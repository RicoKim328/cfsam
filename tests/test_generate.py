# SPDX-License-Identifier: Apache-2.0
"""Generate tests: startup scripts from the golden mission.yaml."""
from cfsam.cli import main
from cfsam.generate import startup_script
from cfsam.importer import _StartupScript
from cfsam.validate import load

from conftest import GOLDEN_DIR
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
    ]
    first = (out / "cpu1" / "cfe_es_startup.scr").read_text(encoding="utf-8").splitlines()[0]
    assert first == "CFE_LIB, cfe_assert, CFE_Assert_LibInit, ASSERT_LIB, 0, 0, 0x0, 0;"


def test_cli_generate_refuses_on_errors(tmp_path, capsys):
    model = load(GOLDEN)
    model["cpus"][0]["startup"].append(entry("CFE_APP", "no_such_app", "NOPE"))
    out = tmp_path / "out"
    assert main(["generate", str(write(tmp_path, model)), "-o", str(out)]) == 1
    assert "startup-unknown-module" in capsys.readouterr().out
    assert not out.exists()
