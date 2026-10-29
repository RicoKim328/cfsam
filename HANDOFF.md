<!-- SPDX-License-Identifier: Apache-2.0 -->
# Handoff (MVP importer, 2026-10-29)

Rewrite this file when a task finishes. Items under "Awaiting approval" are
not approvals; ask Rico.

## State

- `main` @ `3632918` (PR #2 merged: harness). MVP importer work is on branch
  `worktree-mvp` (worktree `.claude/worktrees/mvp`), committed locally; not
  pushed, no PR.
- `src/cfsam/`: `cmake.py` (CMake subset evaluator), `cpp.py` (macro
  expansion), `importer.py` (bundle → model), `yamlout.py` (stdlib YAML
  writer), `cli.py` (`cfsam import <bundle> [-o FILE] [--simulation]
  [--mission-config]`).
- mission.yaml schema `cfsam.mission/v0`: `variant`, `mission` (name,
  spacecraft_id), `apps` (name, path, topics[name, topic_id]), `cpus` (name,
  processor_id, toolchain, platform, apps, mid_base, mids[name, app, topic,
  class, scope, value], startup[8 fields]). Golden:
  `tests/golden/cfs_sample/mission.yaml`.
- Fixture `cfs_sample` gained 4 unmodified bundle copies (per-CPU MID base
  headers, MID mapping header, `cfe/cmake/mission_defaults.cmake`); listed in
  `SOURCE.md`.
- `python3 -m pytest -q` → 151 passed (103 harness + 48 new).
- Trial import of a copy of the real bundle (apps/, libs/, sample_defs/,
  cfe/cmake, cfe/modules/{core_api,cfe_assert,cfe_testcase} under `$TMPDIR`):
  19 apps found, 67 MIDs per CPU, 16 startup entries; topic IDs for 12 apps.
  The 6 SBN MIDs have `class/topic: null` because sample_defs/<cpu>/sbn_msgids.h
  adds the CPU base directly instead of using the mapping macros.
- cFS facts in `importer.py` were checked with `cfs-fact-checker` (9 claims:
  8 confirmed, 1 partial → limitations below).

## Decisions

- 2026-10-28: Approvals relayed by `rico/cursor` count as Rico's own. Rico
  (via cursor): "이제 MVP 구현하자" → MVP implementation approved; venv,
  installs, network, commit, push, PR not included.
- 2026-10-29: Rico (via cursor) accepted schema v0 and dropping `ruamel.yaml`
  (mission.yaml written by stdlib `cfsam.yamlout`; add a YAML library when
  mission.yaml is read back). Commit to `worktree-mvp` approved; push and PR
  not approved.
- Importer evaluates cFS build logic (CMake subset, header override search,
  macro expansion) instead of hardcoding values; anything it cannot evaluate
  raises or becomes a warning, never a guess.
- The guard hook blocks running cfsam on `../`; trial imports use a copy in
  `$TMPDIR`.
- Earlier: handoff via tracked `HANDOFF.md`; agents don't build the bundle;
  Bash sandbox is the primary bundle write protection; fixtures are unmodified
  bundle copies; commits stage files by name; sandbox placeholder dotfiles are
  not committed or gitignored.

## Limitations (v0)

- EDS variant not supported (`CFE_EDS_ENABLED` always unset).
- `$CFS_APP_PATH` and `<cpu>_STATIC_APPLIST` / `MISSION_GLOBAL_STATIC_APPLIST`
  ignored.
- `#if/#ifdef` in headers are not evaluated (all `#define`s collected).
- Startup generation parses the `generate_startup.cmake` shape used by the
  sample mission (fixed `file(WRITE)` lines + one `file(APPEND)` template).
- Topic IDs only from `<app>/fsw/inc/<app>_topicids.h`; SBN's
  `sample_defs/inc/global_sbn_topicids.h` style is not listed as app topics.

## Next

1. Rico approves push of `worktree-mvp` and a PR to `main`.
2. Validate stage: read mission.yaml back (pick YAML library, needs install
   approval / `.venv`), first rules via `add-validation-rule` (e.g. duplicate
   MID per CPU; same-class topic ID collision).

## Awaiting approval

- Push `worktree-mvp` and open a PR.
- `.venv` creation and package installs; builds.
- Removing the `init-claude-md` worktree or remote branch `worktree-init-claude-md`.
