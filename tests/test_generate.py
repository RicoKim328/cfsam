# SPDX-License-Identifier: Apache-2.0
"""Generate tests: startup scripts and topic ID headers from the golden mission.yaml."""
import shutil

from cfsam.cli import main, render
from cfsam.generate import startup_script, topicid_values_header, write_topicid_headers
from cfsam.importer import _StartupScript, import_mission
from cfsam.validate import load

from conftest import FIXTURES_DIR, GOLDEN_DIR
from test_validate import entry, write

GOLDEN = GOLDEN_DIR / "cfs_sample" / "mission.yaml"


def test_startup_script_golden(golden):
    model = load(GOLDEN)
    for cpu in model["cpus"]:
        golden.check(f"cfs_sample/generate/{cpu['name']}/cfe_es_startup.scr", startup_script(cpu))


def test_startup_script_round_trips():
    # Read back with the importer's line parser: same entries as mission.yaml.
    model = load(GOLDEN)
    for cpu in model["cpus"]:
        lines = startup_script(cpu).splitlines()
        parsed = [_StartupScript._parse_line(None, line) for line in lines]
        expected = [{k: v for k, v in e.items() if k != "entry_source"} for e in cpu["startup"]]
        assert [{k: int(v) if isinstance(v, int) else v for k, v in e.items()} for e in parsed] == expected


def test_startup_script_line_format():
    cpu = {"name": "cpu1", "startup": [entry("CFE_APP", "hk", "HK")]}
    cpu["startup"][0]["load_addr"] = 0x20
    assert startup_script(cpu) == "CFE_APP, hk, HK_Main, HK, 50, 16384, 0x20, 0;\n"


def test_cli_generate(tmp_path):
    out = tmp_path / "out"
    assert main(["generate", str(GOLDEN), "-o", str(out)]) == 0
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()) == [
        "cpu1/cfe_es_startup.scr",
        "cpu2/cfe_es_startup.scr",
        "sample_app_topicid_values.h",
    ]
    first = (out / "cpu1" / "cfe_es_startup.scr").read_text(encoding="utf-8").splitlines()[0]
    assert first == "CFE_LIB, cfe_assert, CFE_Assert_LibInit, ASSERT_LIB, 0, 0, 0x0, 0;"


def _app(model, name):
    return next(a for a in model["apps"] if a["name"] == name)


def test_topicid_values_header_golden(golden):
    model = load(GOLDEN)
    golden.check("cfs_sample/generate/sample_app_topicid_values.h", topicid_values_header(_app(model, "sample_app")))


def _bundle_with_headers(tmp_path, model):
    # Generated headers go to <MISSION_DEFS>/, where cFS looks for the override
    # (cfe/cmake/global_functions.cmake:54-92).
    root = tmp_path / "bundle"
    shutil.copytree(FIXTURES_DIR / "cfs_sample", root)
    write_topicid_headers(model, root / "sample_defs")
    return root


def test_topicid_headers_round_trip(tmp_path):
    # The override reproduces the same model: re-import gives the golden file.
    root = _bundle_with_headers(tmp_path, load(GOLDEN))
    text, _ = render(root)
    assert text == GOLDEN.read_text(encoding="utf-8")


def test_topicid_header_edit_moves_mid(tmp_path):
    model = load(GOLDEN)
    topics = _app(model, "sample_app")["topics"]
    next(t for t in topics if t["name"] == "CMD")["topic_id"] = 0x90
    root = _bundle_with_headers(tmp_path, model)
    imported, _ = import_mission(root)
    assert next(t for t in _app(imported, "sample_app")["topics"] if t["name"] == "CMD")["topic_id"] == 0x90
    cpu1 = imported["cpus"][0]
    assert [m["value"] for m in cpu1["mids"] if m["name"] == "SAMPLE_APP_CMD_MID"] == [0x1890]


def test_topicid_headers_skip_apps_without_tidval(tmp_path):
    model = load(GOLDEN)
    _app(model, "sample_app")["tidval"] = None
    assert write_topicid_headers(model, tmp_path) == []


def test_cli_generate_refuses_on_errors(tmp_path, capsys):
    model = load(GOLDEN)
    model["cpus"][0]["startup"].append(entry("CFE_APP", "no_such_app", "NOPE"))
    out = tmp_path / "out"
    assert main(["generate", str(write(tmp_path, model)), "-o", str(out)]) == 1
    assert "startup-unknown-module" in capsys.readouterr().out
    assert not out.exists()
