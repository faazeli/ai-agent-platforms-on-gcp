"""Offline checks for Track B (Harness).

The central promise of the track is "the same CostPilot pipeline, built in Harness".
These tests hold it to that: the Harness eval gate runs the same Job as the Argo
AnalysisTemplate, deploys the same overlays, and lands on the same NetworkPolicies.

Tools are used when present and skipped otherwise:
  kustomize, opa, shellcheck, hadolint, and Harness's JSON schema (set
  HARNESS_SCHEMA_DIR to a folder with pipeline.json and trigger.json, or allow the
  test to download them from github.com/harness/harness-schema).
"""

import json
import os
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path

import pytest
import yaml

PHASE = Path(__file__).resolve().parents[1]
HARNESS = PHASE / "harness"
SCHEMA_URL = "https://raw.githubusercontent.com/harness/harness-schema/main/v0/{name}"


def load(path):
    return yaml.safe_load((HARNESS / path).read_text())


def have(tool):
    return shutil.which(tool) is not None


PIPELINE = load("pipelines/costpilot.yaml")["pipeline"]
STAGES = {s["stage"]["identifier"]: s["stage"] for s in PIPELINE["stages"]}


def steps(node):
    """Every step under node, in order, through step groups and parallel blocks."""
    found = []
    if isinstance(node, dict):
        if "step" in node:
            found.append(node["step"])
        for value in node.values():
            found += steps(value)
    elif isinstance(node, list):
        for item in node:
            found += steps(item)
    return found


def stage_steps(identifier):
    return steps(STAGES[identifier]["spec"]["execution"]["steps"])


def eval_job_from_pipeline():
    """The Job manifest inside the canary_evals step's heredoc, with variables filled in."""
    step = next(s for s in stage_steps("deploy_dev") if s["identifier"] == "canary_evals")
    script = step["spec"]["source"]["spec"]["script"]
    manifest = re.search(r"<<EOF[^\n]*\n(.*?)\nEOF", script, re.S).group(1)
    min_accuracy = next(v["value"] for v in PIPELINE["variables"] if v["name"] == "min_eval_accuracy")
    manifest = (manifest.replace("${JOB}", "agent-evals-1").replace("${IMAGE}", "IMAGE")
                .replace("${MIN_ACCURACY}", min_accuracy))
    return step, script, yaml.safe_load(manifest)


# --------------------------------------------------------------- pipeline shape


def test_stages_mirror_track_a():
    assert list(STAGES) == ["build", "deploy_dev", "approve_prod", "deploy_prod"]
    assert [STAGES[s]["type"] for s in STAGES] == ["CI", "Deployment", "Approval", "Deployment"]
    # Prod deploys the service (and so the digests) that dev proved.
    assert STAGES["deploy_prod"]["spec"]["service"] == {"useFromStage": {"stage": "deploy_dev"}}


def test_dev_canary_is_gated_by_evals_then_cv():
    order = [s["identifier"] for s in stage_steps("deploy_dev")]
    assert order == ["canary_deploy", "canary_evals", "verify", "canary_delete", "rolling_deploy"]
    for identifier in ("deploy_dev", "deploy_prod"):
        stage = STAGES[identifier]
        assert stage["failureStrategies"][0]["onFailure"]["action"]["type"] == "StageRollback"
        rollback = [s["type"] for s in steps(stage["spec"]["execution"]["rollbackSteps"])]
        assert rollback == ["K8sCanaryDelete", "K8sRollingRollback"]


def test_approval_is_by_someone_else():
    approval = stage_steps("approve_prod")[0]["spec"]
    assert approval["approvers"]["disallowPipelineExecutor"] is True
    assert approval["approvers"]["minimumCount"] >= 1


def test_harness_eval_job_is_the_argo_analysis_job():
    """Same image, command, threshold, identity, label, secrets and hardening as Track A."""
    argo = list(yaml.safe_load_all((PHASE / "deploy/rollouts/agents-canary.yaml").read_text()))
    template = next(d for d in argo if d["kind"] == "AnalysisTemplate")
    argo_job = template["spec"]["metrics"][0]["provider"]["job"]["spec"]
    _, _, harness_job = eval_job_from_pipeline()
    a, h = argo_job["template"], harness_job["spec"]["template"]
    assert h["metadata"]["labels"] == a["metadata"]["labels"] == {"app": "agent-evals"}
    for key in ("serviceAccountName", "restartPolicy", "securityContext"):
        assert h["spec"][key] == a["spec"][key], key
    ac, hc = a["spec"]["containers"][0], h["spec"]["containers"][0]
    for key in ("command", "envFrom", "securityContext"):
        assert hc[key] == ac[key], key
    assert harness_job["spec"]["backoffLimit"] == argo_job["backoffLimit"] == 0


def test_eval_job_runs_the_canary_digest():
    step, _, _ = eval_job_from_pipeline()
    image = next(v["value"] for v in step["spec"]["environmentVariables"] if v["name"] == "IMAGE")
    assert "/agents@<+pipeline.stages.build." in image and image.endswith(".AGENTS_DIGEST>")


def test_eval_pods_are_allowed_by_network_policy():
    docs = list(yaml.safe_load_all((PHASE / "deploy/k8s/base/networkpolicies.yaml").read_text()))
    selected = [d["metadata"]["name"] for d in docs if d and d["spec"]["podSelector"].get("matchLabels") == {"app": "agent-evals"}]
    assert selected, "no egress policy for app=agent-evals: the default-deny would starve the eval job"


def test_inline_eval_script_is_valid_shell(tmp_path):
    _, script, _ = eval_job_from_pipeline()
    path = tmp_path / "canary_evals.sh"
    path.write_text(script)
    subprocess.run(["bash", "-n", str(path)], check=True)
    if have("shellcheck"):
        subprocess.run(["shellcheck", "-s", "bash", str(path)], check=True)


# ----------------------------------------------------------- references resolve


def _expressions(text, pattern):
    return set(re.findall(pattern, text))


def test_expressions_point_at_things_that_exist():
    text = "\n".join(p.read_text() for p in [HARNESS / "pipelines/costpilot.yaml",
                                              HARNESS / "kustomize/patches/images.yaml",
                                              HARNESS / "services/costpilot_agents.yaml"])
    declared = {v["name"] for v in PIPELINE["variables"]}
    assert _expressions(text, r"<\+pipeline\.variables\.(\w+)>") <= declared

    build_steps = {s["identifier"]: s for s in stage_steps("build")}
    for step_id, var in _expressions(text, r"steps\.(\w+)\.output\.outputVariables\.(\w+)>"):
        outputs = {o["name"] for o in build_steps[step_id]["spec"]["outputVariables"]}
        assert var in outputs, (step_id, var)
    # ...and the sourced script really sets them.
    script = (HARNESS / "scripts/resolve_digests.sh").read_text()
    for o in build_steps["digests"]["spec"]["outputVariables"]:
        assert re.search(rf"^{o['name']}=", script, re.M), o["name"]


def test_entities_reference_each_other():
    connectors = {load(f"connectors/{p.name}")["connector"]["identifier"] for p in (HARNESS / "connectors").glob("*.yaml")}
    used = set()
    for path in HARNESS.rglob("*.yaml"):
        if "kustomize" in path.parts:
            continue
        used |= set(re.findall(r"connectorRef: (\w+)", path.read_text()))
    assert used <= connectors, used - connectors

    service = load("services/costpilot_agents.yaml")["service"]["identifier"]
    assert STAGES["deploy_dev"]["spec"]["service"]["serviceRef"] == service
    for stage, env in (("deploy_dev", "dev"), ("deploy_prod", "prod")):
        spec = STAGES[stage]["spec"]["environment"]
        assert spec["environmentRef"] == load(f"environments/{env}.yaml")["environment"]["identifier"]
        infra = load(f"infrastructure/gke_{env}.yaml")["infrastructureDefinition"]
        assert spec["infrastructureDefinitions"] == [{"identifier": infra["identifier"]}]
        assert infra["environmentRef"] == env and infra["spec"]["namespace"] == "costpilot"
        # The kustomize folder the service picks with <+env.identifier> exists.
        assert (HARNESS / "kustomize" / env / "kustomization.yaml").exists()

    # Delegate selectors match the names install.sh gives delegates (costpilot-gke-<env>).
    selectors = set(re.findall(r"- (costpilot-gke-\w+)", "\n".join(p.read_text() for p in HARNESS.rglob("*.yaml"))))
    assert selectors and all(s in {"costpilot-gke-dev", "costpilot-gke-prod"} for s in selectors)
    assert 'NAME="costpilot-gke-${ENV}"' in (HARNESS / "delegate/install.sh").read_text()


# --------------------------------------------------------------------- manifests


def build(folder):
    if not have("kustomize"):
        pytest.skip("kustomize not installed")
    out = subprocess.run(["kustomize", "build", str(folder)], check=True, capture_output=True, text=True).stdout
    return [d for d in yaml.safe_load_all(out) if d]


@pytest.mark.parametrize("env", ["dev", "prod"])
def test_agents_is_the_only_managed_workload(env):
    docs = build(HARNESS / "kustomize" / env)
    managed = [d["metadata"]["name"] for d in docs if d["kind"] == "Deployment"
               and (d["metadata"].get("annotations") or {}).get("harness.io/direct-apply") != "true"]
    assert managed == ["agents"]
    assert not [d for d in docs if d["kind"] == "Namespace"], "the delegate may not manage namespaces"
    # Everything else Argo CD would deploy, Harness deploys too.
    track_a = {(d["kind"], d["metadata"]["name"]) for d in build(PHASE / "deploy/k8s/overlays" / env)}
    track_b = {(d["kind"], d["metadata"]["name"]) for d in docs}
    assert track_a - track_b == {("Namespace", "costpilot")}


def test_image_patch_pins_every_image_to_an_attested_digest(tmp_path):
    """Simulate what Harness does: append the Kustomize Patches file to the build."""
    shutil.copytree(HARNESS / "kustomize", tmp_path / "harness/kustomize")
    shutil.copytree(PHASE / "deploy", tmp_path / "deploy")
    folder = tmp_path / "harness/kustomize/dev"
    shutil.copy(HARNESS / "kustomize/patches/images.yaml", folder / "harness-patch-0.yaml")
    data = yaml.safe_load((folder / "kustomization.yaml").read_text())
    data["patchesStrategicMerge"] = ["harness-patch-0.yaml"]  # what Harness adds
    (folder / "kustomization.yaml").write_text(yaml.safe_dump(data))
    images = {d["metadata"]["name"]: d["spec"]["template"]["spec"]["containers"][0]["image"]
              for d in build(tmp_path / "harness/kustomize/dev") if d["kind"] == "Deployment"}
    for svc in ("agents", "cost-api", "mcp-finops"):
        assert re.fullmatch(rf"<\+pipeline\.variables\.registry>/{svc}@<\+pipeline\.stages\.build\..+_DIGEST>", images[svc]), images[svc]


# --------------------------------------------------------------- schema & tools


def harness_schema(name):
    folder = os.environ.get("HARNESS_SCHEMA_DIR")
    if folder and (Path(folder) / name).exists():
        return json.loads((Path(folder) / name).read_text())
    try:
        with urllib.request.urlopen(SCHEMA_URL.format(name=name), timeout=30) as response:
            return json.loads(response.read())
    except Exception as exc:  # offline, or GitHub unreachable
        pytest.skip(f"Harness schema unavailable: {exc}")


@pytest.mark.parametrize("schema_name,document", [("pipeline.json", "pipelines/costpilot.yaml"),
                                                  ("trigger.json", "triggers/push_main.yaml")])
def test_matches_harness_schema(schema_name, document):
    jsonschema = pytest.importorskip("jsonschema")
    validator = jsonschema.Draft7Validator(harness_schema(schema_name))
    errors = [f"{'/'.join(map(str, e.absolute_path))}: {e.message[:200]}" for e in validator.iter_errors(load(document))]
    assert not errors, errors


def test_policies():
    if not have("opa"):
        pytest.skip("opa not installed")
    subprocess.run(["opa", "test", str(HARNESS / "policies")], check=True)
    result = subprocess.run(["opa", "eval", "--format", "json", "--stdin-input", "-d",
                             str(HARNESS / "policies/costpilot_delivery.rego"), "data.pipeline.deny"],
                            input=json.dumps({"pipeline": PIPELINE}), check=True, capture_output=True, text=True)
    assert json.loads(result.stdout)["result"][0]["expressions"][0]["value"] == []


def test_scripts_and_dockerfile():
    for script in [*(HARNESS / "scripts").glob("*.sh"), HARNESS / "delegate/install.sh"]:
        shell = "sh" if script.read_text().startswith("#!/bin/sh") else "bash"
        subprocess.run([shell, "-n", str(script)], check=True)
        if have("shellcheck"):
            subprocess.run(["shellcheck", "-s", shell, str(script)], check=True)
    if have("hadolint"):
        subprocess.run(["hadolint", str(HARNESS / "delegate/Dockerfile")], check=True)
