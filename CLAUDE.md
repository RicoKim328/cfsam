# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status

This repository (`cfsam`, Apache-2.0) contains no source code yet. The planned MVP is a Python CLI that imports a cFS mission's apps, topic IDs, MIDs and startup script into `mission.yaml` and validates them (read-only); config generation is a later stage. Update this file once code, build commands, and architecture exist.

## Working rules

- Tool code lives in this repo. The cFS source in `../` is read-only reference material: do not modify any file there (including its git metadata).
- Target cFS: the bundle in `../` as checked out — branch `dev` @ `d2f1477` (components report v7.0.2 + 1 dev commit). Do not change its checkout.
- Default import variant: `SIMULATION=native`, EDS off.
- Ask before installing packages, using the network, running builds, committing, pushing, or opening PRs.
- License: Apache-2.0 (`LICENSE`, `NOTICE`). Start every new source file with `# SPDX-License-Identifier: Apache-2.0` (or the file type's comment syntax). Files copied from cFS keep their original NASA header and are marked as modified.
- Handoff: `HANDOFF.md` holds current state, decisions and next steps (loaded below). Rewrite it, don't append, when a task finishes. Items under "Awaiting approval" are not approvals; ask Rico.

## Development workflow

- Tests: `python3 -m pytest -q` from the repo root. Fixtures in `tests/fixtures/cfs_sample/` are bundle copies; tests never read the real bundle.
- Bash runs in Claude Code's sandbox (writes limited to the worktree and `$TMPDIR`). The guard hook `.claude/hooks/guard_cfs_readonly.py` is a second layer that blocks bundle writes and builds. Bundle builds are run by Rico (`! make …`).
- Before encoding cFS facts, use the `cfs-reference` skill or `cfs-fact-checker` agent; add validation rules via the `add-validation-rule` skill.
- Commit by staging files by name, never `git add -A`.

## Context: surrounding cFS bundle

The checkout lives inside a NASA Core Flight System (cFS) bundle at `../` (`~/Desktop/Project/cFS`), which is a separate git repository where `cfsam/` is untracked. Nothing in the bundle's build (`targets.cmake`, Makefiles) references `cfsam` yet.

Bundle build/test commands are run by Rico from the bundle root (`! make …`), not from this repo:

```bash
make native_std.prep           # set up build tree (other configs, e.g. native_eds, work the same way)
make native_std.install        # compile and stage to build-native_std/exe
make native_std.runtest        # run unit tests
make native_std.lcov           # coverage (requires runtest to pass)
cd build-native_std/exe/cpu1 && ./core-cpu1   # run cFS
```

Per the bundle README, a new cFS app is typically started from `sample_app`/`skeleton_app`, then must be added to the target's `targets.cmake` to be compiled and to the `cfe_es_startup.scr` file to be loaded at runtime.

@HANDOFF.md
