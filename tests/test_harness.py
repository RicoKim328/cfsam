# SPDX-License-Identifier: Apache-2.0
"""Tests for the development harness itself (guard hook, fixtures, golden)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / ".claude" / "hooks" / "guard_cfs_readonly.py"


@pytest.fixture
def layout(tmp_path):
    """A fake bundle: <tmp>/cfs/{cfe/, cfsam/}."""
    bundle = tmp_path / "cfs"
    cfsam = bundle / "cfsam"
    (bundle / "cfe").mkdir(parents=True)
    cfsam.mkdir()
    return bundle, cfsam


def run_hook(cfsam: Path, tool: str, tool_input: dict, cwd: Path, **env: str) -> subprocess.CompletedProcess:
    event = {"tool_name": tool, "tool_input": tool_input, "cwd": str(cwd)}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env={"CFSAM_ROOT": str(cfsam), "PATH": "", **env},
    )


@pytest.mark.parametrize(
    "tool, tool_input, blocked",
    [
        ("Write", {"file_path": "{bundle}/cfe/x.c"}, True),
        ("Edit", {"file_path": "../cfe/x.c"}, True),
        ("Write", {"file_path": "{cfsam}/src/x.py"}, False),
        ("Write", {"file_path": "{cfsam}/.claude/worktrees/w/x.py"}, False),
        ("Write", {"file_path": "/tmp/elsewhere.txt"}, False),
        ("Bash", {"command": "cat ../cfe/x.c | grep foo"}, False),
        ("Bash", {"command": "cp ../cfe/x.c tests/fixtures/"}, False),
        ("Bash", {"command": "git -C .. log --oneline -1"}, False),
        ("Bash", {"command": "ls 2>&1 > out.txt"}, False),
        ("Bash", {"command": "rm -rf ../cfe"}, True),
        ("Bash", {"command": "echo hi > ../cfe/x.c"}, True),
        ("Bash", {"command": "echo hi >>../cfe/x.c"}, True),
        ("Bash", {"command": "sed -i s/a/b/ ../cfe/x.c"}, True),
        ("Bash", {"command": "cp x.c ../cfe/"}, True),
        ("Bash", {"command": "git -C .. checkout main"}, True),
        ("Bash", {"command": "cd .. && git stash"}, True),
        ("Bash", {"command": "cd ../cfe && touch y"}, True),
        # read-only access stays allowed
        ("Bash", {"command": "grep -rn foo .. | head"}, False),
        ("Bash", {"command": "find .. -name '*.h'"}, False),
        ("Bash", {"command": "sed -n 1,5p ../cfe/x.c"}, False),
        ("Bash", {"command": "cd .. && ls && git log -1"}, False),
        ("Bash", {"command": "cp -r ../cfe/x.c ../cfe/y.c tests/fixtures/"}, False),
        ("Bash", {"command": "for f in a b; do cp {bundle}/cfe/$f tests/; done"}, False),
        ("Bash", {"command": "python3 -m pytest -q"}, False),
        # ordinary writes that a verb blacklist would miss
        ("Bash", {"command": "cat x>../cfe/y"}, True),
        ("Bash", {"command": "make &>../cfe/log"}, True),
        ("Bash", {"command": "cd .. && make native_std.prep"}, True),
        ("Bash", {"command": "perl -pi -e s/a/b/ ../cfe/x.c"}, True),
        ("Bash", {"command": "dd if=x of=../cfe/y"}, True),
        ("Bash", {"command": "tar -xf a.tar -C ../cfe"}, True),
        ("Bash", {"command": "find .. -name x -delete"}, True),
        ("Bash", {"command": "python3 -c \"open('../cfe/x', 'w')\""}, True),
        ("Bash", {"command": "cp -t ../cfe x.c"}, True),
        ("Bash", {"command": "git --git-dir=../.git fetch"}, True),
        ("Bash", {"command": "cd .. ; touch x"}, True),
        ("Bash", {"command": "pushd ../cfe\nrm x"}, True),
        ("Bash", {"command": "find .. -name '*.h' | xargs grep -l foo"}, False),
        ("Bash", {"command": "for f in *.py; do wc -l $f; done"}, False),
        # indirection, links, ancestors and write options of read commands
        ("Bash", {"command": "find .. -name x | xargs rm"}, True),
        ("Bash", {"command": "B=..; rm -rf $B/cfe"}, True),
        ("Bash", {"command": "cat ../cfe/list | while read f; do rm \"$f\"; done"}, True),
        ("Bash", {"command": "rm -rf {bundle}/.."}, True),
        ("Bash", {"command": "ln ../cfe/x.c tests/hard"}, True),
        ("Bash", {"command": "cp -l ../cfe/x.c tests/"}, True),
        ("Bash", {"command": "rsync --remove-source-files ../cfe/x.c tests/"}, True),
        ("Bash", {"command": "sort -o ../cfe/x.c y"}, True),
        ("Bash", {"command": "git -C .. diff --output=../cfe/p"}, True),
        ("Bash", {"command": "sed -n 'w ../cfe/y' x"}, True),
        ("Bash", {"command": "sed -n '1e rm x' ../cfe/x.c"}, True),
        ("Bash", {"command": "awk '{{print > \"../cfe/y\"}}' x"}, True),
        ("Bash", {"command": "sed -n 's/a/b/w ../cfe/y' x"}, True),
        ("Bash", {"command": "sed -e 's/the end/x/' ../cfe/x.c"}, False),
        # variable targets, unknown cwd, substitutions, globs, option forms
        ("Bash", {"command": "B=..; echo x > $B/y"}, True),
        ("Bash", {"command": "B=..; cd $B && touch x"}, True),
        ("Bash", {"command": "pushd ../cfe; pushd /tmp; popd; rm x"}, True),
        ("Bash", {"command": "echo x > >(tee ../cfe/y)"}, True),
        ("Bash", {"command": "echo $(rm ../cfe/x)"}, True),
        ("Bash", {"command": "echo `rm ../cfe/x`"}, True),
        ("Bash", {"command": "(cd .. && touch x)"}, True),
        ("Bash", {"command": "rm -rf {bundle}/../cf?"}, True),
        ("Bash", {"command": "rm -rf ../{{cfe,x}}"}, True),
        ("Bash", {"command": "sort -uo ../cfe/x.c y"}, True),
        ("Bash", {"command": "sed -n --expression='w ../cfe/y' x"}, True),
        ("Bash", {"command": "sed -ne 'w ../cfe/y' x"}, True),
        ("Bash", {"command": "git -C .. -c core.pager=./evil log"}, True),
        ("Bash", {"command": "echo \"$(rm ../cfe/x)\""}, True),
        ("Bash", {"command": "echo \"`rm ../cfe/x`\""}, True),
        ("Bash", {"command": "cd ../cfe; (cd /tmp); rm x"}, True),
        ("Bash", {"command": "cd ../cfe; echo `cd /tmp`; rm x"}, True),
        ("Bash", {"command": "rm -rf \"$(dirname $PWD)\"/cfe"}, True),
        ("Bash", {"command": "for d in ../cfe; do rm -rf $d; done"}, True),
        ("Bash", {"command": "touch tests/$UNSET_VAR"}, True),
        ("Bash", {"command": "echo hi > $UNSET_VAR/x"}, True),
        ("Bash", {"command": "for f in a b; do touch tests/$f; done"}, False),
        ("Bash", {"command": "for f in a b; do touch tests/${{f}}.txt; done"}, False),
        # loop variables reassigned in the body are not trusted
        ("Bash", {"command": "for f in a; do f=../cfe/x; rm $f; done"}, True),
        ("Bash", {"command": "for f in a; do read f; rm \"$f\"; done < list"}, True),
        ("Bash", {"command": "for f in a; do declare f=../cfe; rm -r $f; done"}, True),
        ("Bash", {"command": "for f in a; do :; done; for f in ../cfe; do :; done; rm -r $f"}, True),
        ("Bash", {"command": "for f in a; do :; done; f=../cfe; rm -r $f"}, True),
        ("Bash", {"command": "(cd /tmp && touch x)"}, False),
        ("Bash", {"command": "diff <(cat ../cfe/x.c) tests/x.c"}, False),
        ("Bash", {"command": "echo $(git -C .. rev-parse HEAD) > tests/rev"}, False),
        ("Bash", {"command": "rg --pre ./evil foo ../cfe"}, True),
    ],
)
def test_guard(layout, tool, tool_input, blocked):
    bundle, cfsam = layout
    tool_input = {k: v.format(bundle=bundle, cfsam=cfsam) for k, v in tool_input.items()}
    result = run_hook(cfsam, tool, tool_input, cwd=cfsam)
    assert result.returncode == (2 if blocked else 0), result.stderr


def test_guard_expands_environment(layout):
    bundle, cfsam = layout
    result = run_hook(cfsam, "Bash", {"command": "rm -rf $PROJ/../cfe"}, cwd=cfsam, PROJ=str(cfsam))
    assert result.returncode == 2, result.stderr


@pytest.mark.parametrize(
    "command",
    [
        "PROJ=..; rm -rf $PROJ/cfe",
        "export PROJ=../cfe; rm -rf $PROJ",
        "read PROJ < f; rm -rf $PROJ/x",
        "for PROJ in a; do PROJ=../cfe; rm -r $PROJ; done",
        "declare PROJ=..; touch ${PROJ}/cfe/x",
        "HOME=..; rm -rf ~/cfe",
        "export HOME=../cfe; touch ~",
        "HOME=..; X=~/cfe; rm -rf $X",
    ],
)
def test_guard_ignores_stale_environment(layout, command):
    """A variable reassigned in the command must not be expanded from the hook's env."""
    bundle, cfsam = layout
    safe = str(cfsam / "safe")
    result = run_hook(cfsam, "Bash", {"command": command}, cwd=cfsam, PROJ=safe, HOME=safe)
    assert result.returncode == 2, result.stderr


@pytest.mark.parametrize(
    "command, blocked",
    [
        ("touch $PROJ/x", False),
        ("touch ~/x", False),
        ("rm -rf ~/cfe", True),  # HOME is the bundle here
        ("touch --reference=x ~/../cfe/y", True),
    ],
)
def test_guard_uses_untouched_environment(layout, command, blocked):
    bundle, cfsam = layout
    env = {"PROJ": str(cfsam / "safe"), "HOME": str(cfsam / "safe")}
    if command == "rm -rf ~/cfe":
        env["HOME"] = str(bundle)
    if command.startswith("touch --reference"):
        env["HOME"] = str(cfsam)
    result = run_hook(cfsam, "Bash", {"command": command}, cwd=cfsam, **env)
    assert result.returncode == (2 if blocked else 0), result.stderr


@pytest.mark.parametrize(
    "command, blocked",
    [
        ("touch \"$TMPDIR/probe\" && rm \"$TMPDIR/probe\"", False),
        ("echo hi > ${TMPDIR}/x", False),
        ("TMPDIR=..; rm -rf $TMPDIR/cfe", True),  # reassigned: not the sandbox value
    ],
)
def test_guard_resolves_sandbox_tmpdir(layout, command, blocked):
    """TMPDIR unset in the hook's env resolves to the sandbox's /tmp/claude-<uid>."""
    bundle, cfsam = layout
    result = run_hook(cfsam, "Bash", {"command": command}, cwd=cfsam)
    assert result.returncode == (2 if blocked else 0), result.stderr


def test_guard_ignores_other_tools(layout):
    bundle, cfsam = layout
    result = run_hook(cfsam, "Read", {"file_path": str(bundle / "cfe" / "x.c")}, cwd=cfsam)
    assert result.returncode == 0


def test_cfs_fixture(cfs_fixture):
    root = cfs_fixture("sample")
    assert (root / "sample_defs" / "targets.cmake").is_file()
    with pytest.raises(FileNotFoundError):
        cfs_fixture("missing")


def test_golden_roundtrip(tmp_path, monkeypatch):
    import conftest

    monkeypatch.setattr(conftest, "GOLDEN_DIR", tmp_path)
    conftest.Golden(update=True).check("a/b.txt", "x\n")
    conftest.Golden(update=False).check("a/b.txt", "x\n")
    with pytest.raises(pytest.fail.Exception, match="golden mismatch"):
        conftest.Golden(update=False).check("a/b.txt", "y\n")
