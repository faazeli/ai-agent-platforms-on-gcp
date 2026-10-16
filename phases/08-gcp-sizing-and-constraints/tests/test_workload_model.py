"""The worked example from the README must come out exactly as documented."""

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sizing"))
from workload_model import apply_scale, compute, main  # noqa: E402

EXAMPLE = Path(__file__).resolve().parents[1] / "sizing" / "assumptions.example.yaml"


def example():
    return yaml.safe_load(EXAMPLE.read_text())


def test_worked_example_from_the_readme():
    a = example()
    result = compute(a)
    assert result["questions_per_day"] == 1000
    total_calls = sum(load.calls_per_day for load in result["loads"])
    assert total_calls == 6000                                   # 6 model calls per question
    peak_tpm = sum(load.peak_tokens_per_minute for load in result["loads"])
    assert peak_tpm == pytest.approx(114_000)                   # 30 calls/min x 3,800 tokens
    tokens_per_day = sum(load.calls_per_day * 3800 for load in result["loads"])
    assert tokens_per_day == 22_800_000


def test_scaling_users_reveals_the_first_quota_to_break():
    result = compute(apply_scale(example(), {"users": 5}))
    assert result["warnings"], "5x users should exceed a placeholder quota"
    assert any("requests/min" in w or "tokens/min" in w for w in result["warnings"])


def test_cost_per_thousand_questions_is_consistent():
    result = compute(example())
    monthly_questions = 1000 * 22
    assert result["cost_per_1000_questions"] == pytest.approx(result["total_monthly_cost"] / monthly_questions * 1000)


def test_unknown_scale_key_is_an_error():
    with pytest.raises(KeyError):
        apply_scale(example(), {"userz": 2})


def test_cli_exit_code_signals_quota_trouble(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main([str(EXAMPLE), "--scale", "users=5"])
    assert exit_info.value.code == 2
    assert "WARNINGS" in capsys.readouterr().out
