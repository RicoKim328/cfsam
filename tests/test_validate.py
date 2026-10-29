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
    # 0x1982 is SAMPLE_APP_CMD_MID on cpu2 only; reusing it on cpu1 is fine.
    model["cpus"][0]["mids"].append(mid("OTHER_APP_CMD_MID", "other_app", "CMD", "cmd", 0x1982))
    assert validate(model) == []


def test_cmd_and_tlm_sharing_topic_id_pass(model):
    # sample_app SEND_HK and HK_TLM share topic ID 0x83 but are different classes.
    cpu1 = model["cpus"][0]
    topics = {m["topic"]: m for m in cpu1["mids"]}
    assert topics["SEND_HK"]["value"] != topics["HK_TLM"]["value"]
    assert validate(copy.deepcopy(model)) == []


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
