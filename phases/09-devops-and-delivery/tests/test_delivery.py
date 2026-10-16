"""Offline checks for Phase 9's delivery assets.

Runs anywhere with Python. Uses kustomize, kubeconform, hadolint, actionlint and
tofu when they are on PATH (the course's CI installs them) and skips otherwise.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

PHASE = Path(__file__).resolve().parents[1]
K8S = PHASE / "deploy" / "k8s"
sys.path.insert(0, str(PHASE / "dora"))
from dora_metrics import compute  # noqa: E402


def have(tool):
    return shutil.which(tool) is not None


def build(overlay):
    if not have("kustomize"):
        pytest.skip("kustomize not installed")
    out = subprocess.run(["kustomize", "build", str(K8S / "overlays" / overlay)],
                         check=True, capture_output=True, text=True).stdout
    return [d for d in yaml.safe_load_all(out) if d]


@pytest.mark.parametrize("overlay", ["dev", "prod"])
def test_every_workload_is_hardened(overlay):
    docs = build(overlay)
    deployments = [d for d in docs if d["kind"] == "Deployment"]
    assert {d["metadata"]["name"] for d in deployments} == {"cost-api", "mcp-finops", "agents", "litellm"}
    for d in deployments:
        pod = d["spec"]["template"]["spec"]
        assert pod["serviceAccountName"] == d["metadata"]["name"], "one identity per workload"
        assert pod["securityContext"]["runAsNonRoot"] is True
        for c in pod["containers"]:
            assert c["resources"]["requests"]["cpu"] and c["resources"]["requests"]["memory"]
            assert "readinessProbe" in c and "livenessProbe" in c
            assert c["securityContext"]["allowPrivilegeEscalation"] is False
            assert c["securityContext"]["capabilities"]["drop"] == ["ALL"]
            assert not c["image"].endswith(":latest")


def test_workload_identity_annotations_are_filled_in():
    for sa in (d for d in build("prod") if d["kind"] == "ServiceAccount"):
        annotation = sa["metadata"]["annotations"]["iam.gke.io/gcp-service-account"]
        assert annotation.startswith(f"{sa['metadata']['name']}-gsa@") and "@PROJECT_ID." not in annotation  # base token replaced


def test_network_is_default_deny():
    policies = {d["metadata"]["name"]: d for d in build("dev") if d["kind"] == "NetworkPolicy"}
    deny = policies["default-deny-all"]["spec"]
    assert deny["podSelector"] == {} and set(deny["policyTypes"]) == {"Ingress", "Egress"}
    # cost-api accepts traffic only from mcp-finops and ledger-java
    sources = policies["cost-api-from-mcp-and-ledger"]["spec"]["ingress"][0]["from"]
    assert {s["podSelector"]["matchLabels"]["app"] for s in sources} == {"mcp-finops", "ledger-java"}


def test_project_config_map_is_not_deployed():
    assert not any(d["kind"] == "ConfigMap" and d["metadata"]["name"].startswith("project") for d in build("dev"))


@pytest.mark.skipif(not have("kubeconform"), reason="kubeconform not installed")
def test_manifests_match_kubernetes_schemas(tmp_path):
    for overlay in ("dev", "prod"):
        rendered = tmp_path / f"{overlay}.yaml"
        rendered.write_text(yaml.safe_dump_all(build(overlay)))
        subprocess.run(["kubeconform", "-strict", "-summary", str(rendered)], check=True)


@pytest.mark.skipif(not have("hadolint"), reason="hadolint not installed")
def test_dockerfiles_lint_clean():
    for dockerfile in (PHASE / "docker").glob("*.Dockerfile"):
        subprocess.run(["hadolint", str(dockerfile)], check=True)


@pytest.mark.skipif(not have("actionlint"), reason="actionlint not installed")
def test_workflows_lint_clean():
    workflows = sorted(str(p) for p in (PHASE / "ci" / "github-workflows").glob("*.yml"))
    subprocess.run(["actionlint", "-shellcheck=", *workflows], check=True)


@pytest.mark.skipif(not have("tofu"), reason="tofu not installed")
def test_opentofu_is_formatted():
    subprocess.run(["tofu", "fmt", "-check", "-recursive", str(PHASE / "infra" / "tofu")], check=True)


def test_dora_metrics():
    rows = [
        {"deployed_at": "2026-10-01T12:00:00Z", "first_commit_at": "2026-09-30T12:00:00Z",
         "service": "agents", "change_failed": "false", "restored_at": ""},
        {"deployed_at": "2026-10-08T12:00:00Z", "first_commit_at": "2026-10-08T06:00:00Z",
         "service": "cost-api", "change_failed": "true", "restored_at": "2026-10-08T14:00:00Z"},
    ]
    metrics = compute(rows, days=14)
    assert metrics == {"deploys_per_week": 1.0, "lead_time_hours_median": 15.0,
                       "change_failure_rate": 0.5, "time_to_restore_hours_median": 2.0}
