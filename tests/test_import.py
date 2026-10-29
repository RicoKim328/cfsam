# SPDX-License-Identifier: Apache-2.0
"""Importer tests against tests/fixtures/cfs_sample (bundle copies at d2f1477)."""
import shutil

import pytest

from cfsam.cli import main, render
from cfsam.importer import import_mission


@pytest.fixture
def sample(cfs_fixture):
    return cfs_fixture("sample")


@pytest.fixture
def sample_copy(sample, tmp_path):
    root = tmp_path / "bundle"
    shutil.copytree(sample, root)
    return root


def test_golden_mission_yaml(sample, golden):
    text, _ = render(sample)
    golden.check("cfs_sample/mission.yaml", text)


def test_mission_and_cpus(sample):
    model, _ = import_mission(sample)
    assert model["mission"] == {"name": "SampleMission", "spacecraft_id": 0x42}
    assert [c["name"] for c in model["cpus"]] == ["cpu1", "cpu2"]
    cpu1 = model["cpus"][0]
    assert cpu1["toolchain"] == "native"
    assert cpu1["platform"] == ["default", "cpu1"]
    # <cpu>_APPLIST first, then MISSION_GLOBAL_APPLIST (cfe defaults before targets.cmake).
    assert cpu1["apps"][:6] == ["ci_lab", "to_lab", "sch_lab", "cfe_assert", "cfe_testcase", "sample_app"]
    # native and EDS off: the sbn apps are included.
    assert cpu1["apps"][-3:] == ["sbn", "sbn_udp", "sbn_f_remap"]


def test_sample_app_topics_and_mids(sample):
    model, _ = import_mission(sample)
    app = next(a for a in model["apps"] if a["name"] == "sample_app")
    assert app["path"] == "apps/sample_app"
    assert {t["name"]: t["topic_id"] for t in app["topics"]} == {"CMD": 0x82, "SEND_HK": 0x83, "HK_TLM": 0x83}
    expected = {
        "cpu1": {"SAMPLE_APP_CMD_MID": 0x1882, "SAMPLE_APP_SEND_HK_MID": 0x1883, "SAMPLE_APP_HK_TLM_MID": 0x0883},
        "cpu2": {"SAMPLE_APP_CMD_MID": 0x1982, "SAMPLE_APP_SEND_HK_MID": 0x1983, "SAMPLE_APP_HK_TLM_MID": 0x0983},
    }
    for cpu in model["cpus"]:
        assert {m["name"]: m["value"] for m in cpu["mids"]} == expected[cpu["name"]]
    hk = next(m for m in model["cpus"][0]["mids"] if m["name"] == "SAMPLE_APP_HK_TLM_MID")
    assert (hk["topic"], hk["class"], hk["scope"]) == ("HK_TLM", "tlm", "platform")


def test_startup_entries(sample):
    model, _ = import_mission(sample)
    startup = model["cpus"][0]["startup"]
    assert [e["name"] for e in startup] == [
        "ASSERT_LIB", "SAMPLE_LIB", "SCH_LAB", "CI_LAB", "TO_LAB", "SAMPLE_APP",
        "LC", "CF", "DS", "FM", "HK", "HS", "SC", "MD", "CS", "SBN",
    ]
    assert startup[6] == {
        "type": "CFE_APP", "file": "lc", "entry": "LC_AppMain", "name": "LC",
        "priority": 70, "stack": 131072, "load_addr": 0, "exception_action": 0,
    }


def test_missing_app_sources_are_warnings(sample):
    _, warnings = import_mission(sample)
    assert "app ci_lab: source directory not found in module search path" in warnings
    assert not any("sample_app" in w for w in warnings)


def test_rtems5_variant_drops_cpu2_and_sbn(sample):
    model, _ = import_mission(sample, simulation="i686-rtems5")
    assert [c["name"] for c in model["cpus"]] == ["cpu1"]
    assert "sbn" not in model["cpus"][0]["apps"]
    assert "SBN" not in [e["name"] for e in model["cpus"][0]["startup"]]


def test_cpu_specific_msgids_override(sample_copy):
    # A <defs>/<cpu>/ file wins over the app's default_* config file.
    override = sample_copy / "sample_defs/cpu2/sample_app_msgids.h"
    override.write_text("#define SAMPLE_APP_CMD_MID 0x1999\n")
    model, _ = import_mission(sample_copy)
    cpu1, cpu2 = model["cpus"]
    assert [m["value"] for m in cpu1["mids"] if m["name"] == "SAMPLE_APP_CMD_MID"] == [0x1882]
    assert cpu2["mids"] == [
        {"name": "SAMPLE_APP_CMD_MID", "app": "sample_app", "topic": None, "class": None, "scope": None, "value": 0x1999}
    ]


def test_sb_highest_valid_msgid(sample):
    model, _ = import_mission(sample)
    assert [c["sb_highest_valid_msgid"] for c in model["cpus"]] == [0x1FFF, 0x1FFF]


def test_sb_highest_valid_msgid_cpu_override(sample_copy):
    # cfe/modules/sb/arch_build.cmake: cfe_sb_internal_cfg_values.h is a per-CPU config file.
    (sample_copy / "sample_defs/cpu2/cfe_sb_internal_cfg_values.h").write_text(
        "#define CFE_PLATFORM_SB_CFGVAL(x) CPU2_SB_##x\n#define CPU2_SB_HIGHEST_VALID_MSGID 0xFFFF\n"
    )
    model, _ = import_mission(sample_copy)
    assert [c["sb_highest_valid_msgid"] for c in model["cpus"]] == [0x1FFF, 0xFFFF]


def test_sb_highest_valid_msgid_missing_is_warning(sample_copy):
    (sample_copy / "cfe/modules/sb/fsw/inc/cfe_sb_internal_cfg.h").unlink()
    model, warnings = import_mission(sample_copy)
    assert [c["sb_highest_valid_msgid"] for c in model["cpus"]] == [None, None]
    assert any("cpu1: CFE_PLATFORM_SB_HIGHEST_VALID_MSGID" in w for w in warnings)


def test_mission_topicid_values_override(sample_copy):
    (sample_copy / "sample_defs/sample_app_topicid_values.h").write_text(
        "#define SAMPLE_APP_MISSION_TIDVAL(x) (0x40 + DEFAULT_SAMPLE_APP_MISSION_##x##_TOPICID)\n"
    )
    model, _ = import_mission(sample_copy)
    app = next(a for a in model["apps"] if a["name"] == "sample_app")
    assert app["topics"][0] == {"name": "CMD", "topic_id": 0xC2}


def test_cfe_mission_topic_spelling(sample_copy):
    inc = sample_copy / "apps/hs/fsw/inc"
    inc.mkdir(parents=True)
    (inc / "hs_topicids.h").write_text(
        "#define CFE_MISSION_HS_CMD_TOPICID 0xAE\n#define DEFAULT_CFE_MISSION_HS_CMD_TOPICID 0xAE\n"
    )
    model, _ = import_mission(sample_copy)
    app = next(a for a in model["apps"] if a["name"] == "hs")
    assert app["topics"] == [{"name": "CMD", "topic_id": 0xAE}]


def test_cli_writes_file_and_reports_warnings(sample, tmp_path, capsys):
    out = tmp_path / "mission.yaml"
    assert main(["import", str(sample), "-o", str(out)]) == 0
    assert out.read_text().startswith("# Generated by cfsam import")
    assert "cfsam: warning: app ci_lab" in capsys.readouterr().err


def test_cli_error_for_non_bundle(tmp_path, capsys):
    assert main(["import", str(tmp_path)]) == 2
    assert "targets.cmake" in capsys.readouterr().err


def test_import_does_not_modify_bundle(sample_copy):
    before = {p: p.read_bytes() for p in sample_copy.rglob("*") if p.is_file()}
    import_mission(sample_copy)
    after = {p: p.read_bytes() for p in sample_copy.rglob("*") if p.is_file()}
    assert before == after
