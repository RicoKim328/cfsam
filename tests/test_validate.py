# SPDX-License-Identifier: Apache-2.0
"""Validate tests: the golden mission.yaml passes; small models trigger each finding."""
import copy

import pytest
import yaml

from cfsam.cli import main
from cfsam.validate import MissionLoadError, load, validate

from conftest import GOLDEN_DIR

GOLDEN = GOLDEN_DIR / "cfs_sample" / "mission.yaml"


@pytest.fixture
def model():
    return load(GOLDEN)


def mid(name, app, topic, cls, value, scope="platform"):
    return {"name": name, "app": app, "topic": topic, "class": cls, "scope": scope, "value": value}


def write(tmp_path, model):
    path = tmp_path / "mission.yaml"
    path.write_text(yaml.safe_dump(model), encoding="utf-8")
    return path


def test_golden_passes(model):
    assert validate(model) == []


def test_load_rejects_other_schema(tmp_path, model):
    model["schema"] = "cfsam.mission/v1"
    with pytest.raises(MissionLoadError, match="cfsam.mission/v1"):
        load(write(tmp_path, model))


def test_load_rejects_non_mapping(tmp_path):
    path = tmp_path / "mission.yaml"
    path.write_text("- a\n", encoding="utf-8")
    with pytest.raises(MissionLoadError, match="mapping"):
        load(path)


def test_mid_duplicate(model):
    cpu1 = model["cpus"][0]
    cpu1["mids"].append(mid("OTHER_APP_CMD_MID", "other_app", "CMD", "cmd", 0x1882))
    findings = validate(model)
    assert len(findings) == 1
    f = findings[0]
    assert (f.severity, f.rule, f.where) == ("error", "mid-duplicate", "cpu1")
    assert "0x1882" in f.message
    assert "SAMPLE_APP_CMD_MID (sample_app)" in f.message
    assert "OTHER_APP_CMD_MID (other_app)" in f.message
    assert str(f).startswith("error: [mid-duplicate] cpu1: ")


def test_mid_alias_passes(model):
    # sc: SC_1HZ_WAKEUP_MID is defined as SC_WAKEUP_MID (one message, two names).
    cpu1 = model["cpus"][0]
    cpu1["mids"].append(mid("SC_WAKEUP_MID", "sc", "WAKEUP", "cmd", 0x18AB))
    cpu1["mids"].append(mid("SC_1HZ_WAKEUP_MID", "sc", "WAKEUP", "cmd", 0x18AB))
    assert validate(model) == []


def test_mid_duplicate_unknown_topic(model):
    # Without a topic the message identity is unknown, so names count separately.
    cpu1 = model["cpus"][0]
    cpu1["mids"].append(mid("A_MID", "sbn", None, None, 0x18FA, scope=None))
    cpu1["mids"].append(mid("B_MID", "sbn", None, None, 0x18FA, scope=None))
    assert [f.rule for f in validate(model)] == ["mid-duplicate"]


def test_mid_duplicate_is_per_cpu(model):
    # 0x1982 is SAMPLE_APP_CMD_MID on cpu2 only; reusing it on cpu1 is no
    # mid-duplicate, only the mid-cross-cpu warning.
    model["cpus"][0]["mids"].append(mid("OTHER_APP_CMD_MID", "other_app", "CMD", "cmd", 0x1982))
    assert [f.rule for f in validate(model)] == ["mid-cross-cpu"]


def test_cmd_and_tlm_sharing_topic_id_pass(model):
    # sample_app SEND_HK and HK_TLM share topic ID 0x83 but are different classes.
    cpu1 = model["cpus"][0]
    topics = {m["topic"]: m for m in cpu1["mids"]}
    assert topics["SEND_HK"]["value"] != topics["HK_TLM"]["value"]
    assert validate(copy.deepcopy(model)) == []


def test_mid_invalid_above_highest(model):
    model["cpus"][0]["mids"].append(mid("X_CMD_MID", "x", "CMD", "cmd", 0x3082))
    findings = validate(model)
    assert [(f.severity, f.rule, f.where) for f in findings] == [("error", "mid-invalid", "cpu1")]
    assert "X_CMD_MID (x)" in findings[0].message
    assert "0x3082" in findings[0].message and "0x1FFF" in findings[0].message


def test_mid_invalid_zero(model):
    model["cpus"][1]["mids"].append(mid("X_MID", "x", None, None, 0, scope=None))
    assert [(f.rule, f.where) for f in validate(model)] == [("mid-invalid", "cpu2")]


def test_mid_invalid_without_highest_checks_zero_only(model):
    cpu1 = model["cpus"][0]
    cpu1["sb_highest_valid_msgid"] = None
    cpu1["mids"].append(mid("X_CMD_MID", "x", "CMD", "cmd", 0x3082))
    assert validate(model) == []
    cpu1["mids"].append(mid("Y_MID", "y", None, None, 0, scope=None))
    assert [f.rule for f in validate(model)] == ["mid-invalid"]


def test_mid_class_bit(model):
    cpu1 = model["cpus"][0]
    cpu1["mids"].append(mid("X_CMD_MID", "x", "CMD", "cmd", 0x0885))
    cpu1["mids"].append(mid("X_HK_TLM_MID", "x", "HK_TLM", "tlm", 0x1886))
    findings = validate(model)
    assert [(f.severity, f.rule) for f in findings] == [("error", "mid-class-bit")] * 2
    assert "X_CMD_MID (x)" in findings[0].message and "cmd" in findings[0].message
    assert "X_HK_TLM_MID (x)" in findings[1].message and "tlm" in findings[1].message


def test_mid_class_bit_skips_unknown_class(model):
    model["cpus"][0]["mids"].append(mid("X_MID", "x", None, None, 0x0885, scope=None))
    assert validate(model) == []


def test_mid_cross_cpu(model):
    # cpu1 platform topic 0x182 reaches cpu2's CMD base: 0x1800 | 0x182 == 0x1982.
    model["cpus"][0]["mids"].append(mid("X_CMD_MID", "x", "CMD", "cmd", 0x1982))
    findings = validate(model)
    assert [(f.severity, f.rule, f.where) for f in findings] == [("warning", "mid-cross-cpu", "cpu1, cpu2")]
    assert "X_CMD_MID (x) on cpu1" in findings[0].message
    assert "SAMPLE_APP_CMD_MID (sample_app) on cpu2" in findings[0].message


def test_mid_cross_cpu_skips_global_and_unknown_scope(model):
    for cpu in model["cpus"]:
        cpu["mids"].append(mid("TIME_DATA_CMD_MID", "cfe_time", "DATA_CMD", "cmd", 0x1860, scope="global"))
        cpu["mids"].append(mid(f"SBN_{cpu['name']}_MID", "sbn", None, None, 0x18FA, scope=None))
    assert validate(model) == []


def test_cli_validate_ok(capsys):
    assert main(["validate", str(GOLDEN)]) == 0
    assert capsys.readouterr().out == ""


def test_cli_validate_error(tmp_path, model, capsys):
    model["cpus"][1]["mids"].append(mid("X_MID", "x", None, None, 0x1983))
    assert main(["validate", str(write(tmp_path, model))]) == 1
    out = capsys.readouterr().out
    assert out.startswith("error: [mid-duplicate] cpu2: ")


def test_cli_validate_load_error(tmp_path, capsys):
    assert main(["validate", str(tmp_path / "missing.yaml")]) == 2
    assert "cfsam: error:" in capsys.readouterr().err
