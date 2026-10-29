<!-- SPDX-License-Identifier: Apache-2.0 -->
# Handoff (MID range/class/cross-CPU rules, 2026-10-29)

Rewrite this file when a task finishes. Items under "Awaiting approval" are
not approvals; ask Rico.

## State

- `main` @ `3523155` (PR #6 merged: `cfsam validate` + `mid-duplicate`).
  Remote has only `main`; local clean-up of merged worktrees and branches is
  done.
- Branch `worktree-mid-rules` (from `3523155`), worktree
  `.claude/worktrees/mid-rules`: rules A-1 to A-3 below, **uncommitted**
  (commit/push/PR not yet approved).
- `src/cfsam/`: `cmake.py`, `cpp.py`, `importer.py`, `yamlout.py`,
  `validate.py`, `cli.py` (`cfsam import`, `cfsam validate <mission.yaml>`
  → `severity: [rule] where: message`, exit 0 / 1 on errors / 2 on load
  error).
- Schema stays `cfsam.mission/v0`; `cpus[].sb_highest_valid_msgid` added
  (approved 2026-10-29). The importer evaluates
  `CFE_PLATFORM_SB_HIGHEST_VALID_MSGID` from
  `cfe/modules/sb/fsw/inc/cfe_sb_internal_cfg.h:155-156` plus the per-CPU
  `cfe_sb_internal_cfg_values.h` (`cfe/modules/sb/arch_build.cmake`); if it
  cannot, it warns and writes null. Sample: 0x1FFF on cpu1 and cpu2.
- Rules (`validate.RULES`):
  - `mid-duplicate` (error): two different messages on one CPU share a MID.
    Aliases with the same (app, topic, class, scope) pass
    (`SC_1HZ_WAKEUP_MID` = `SC_WAKEUP_MID`); `topic: null` MIDs count per name.
  - `mid-invalid` (error): MID is 0 or above `sb_highest_valid_msgid`
    (only 0 is checked when the field is null).
  - `mid-class-bit` (error): class cmd with bit 0x1000 clear, or tlm with it
    set; `class: null` skipped.
  - `mid-cross-cpu` (warning): the same value as a platform MID on two or more
    CPUs; global and null scopes skipped.
- Fixture `tests/fixtures/cfs_sample` gained
  `cfe/modules/sb/fsw/inc/cfe_sb_internal_cfg.h` and
  `cfe/modules/sb/config/default_cfe_sb_internal_cfg_values.h` (unmodified,
  listed in `SOURCE.md`). Golden: `sb_highest_valid_msgid: 0x1FFF` per CPU.
- `python3 -m pytest -q` → 172 passed.
- Trial on `$TMPDIR/trial/bundle` (copy of apps, cfe, libs, osal, psp,
  sample_defs, tools): import with no warnings, validate with no findings,
  exit 0.
- Sandbox: Bash cannot create directories under `.claude/worktrees/`; use
  EnterWorktree (branch `worktree-<name>`). The guard hook blocks `tar` and
  `find -prune` on the bundle and heredoc commit messages; use `cp -r`, plain
  `find`/`ls`, and `git commit -F <file>`.

## Decisions

- 2026-10-28: Handoff via tracked `HANDOFF.md`, auto-loaded by `@HANDOFF.md`
  in CLAUDE.md; rewritten, not appended.
- 2026-10-28: Approvals relayed by `rico/cursor` count as Rico's own.
- 2026-10-29: Schema `cfsam.mission/v0`, written by stdlib `cfsam.yamlout`,
  read back with PyYAML. Adding fields keeps v0.
- 2026-10-29: No topic-ID rule. MID = base | topic
  (`cfe/modules/core_api/config/default_cfe_core_api_msgid_mapping.h:49-86`)
  and the bundle documents no topic limit, so rules check computed MID values:
  duplicates, SB validity, class bit, cross-CPU reuse.
- 2026-10-29: Severities: `mid-duplicate`, `mid-invalid`, `mid-class-bit`
  error; `mid-cross-cpu` warning (only matters when CPUs share a bus).
  Citations are in `validate.py`.
- 2026-10-29: Startup rules B-1 `startup-unknown-module`, B-2
  `startup-duplicate-name`, B-3 `startup-bad-type` are fact-checked and will be
  errors (ES logs and skips bad lines and keeps starting:
  `cfe/modules/es/fsw/src/cfe_es_startupscript.c:296-300`), but are not
  selected for implementation yet.
- Importer evaluates cFS build logic instead of hardcoding values; anything
  it cannot evaluate raises or becomes a warning, never a guess.
- The guard hook blocks running cfsam on `../`; trial imports use a copy in
  `$TMPDIR`.
- Agents do not build the cFS bundle; Rico runs bundle builds. Merges and
  remote branch deletion are done by Rico outside Claude Code.
- Fixtures are unmodified bundle copies at bundle-relative paths; tests never
  read the real bundle. Validate tests use the golden mission.yaml as the
  passing case and edit it in the test for failing cases.

## Limitations (v0)

- EDS variant not supported (`CFE_EDS_ENABLED` always unset).
- `$CFS_APP_PATH` and `<cpu>_STATIC_APPLIST` / `MISSION_GLOBAL_STATIC_APPLIST`
  ignored.
- `#if/#ifdef` in headers are not evaluated (all `#define`s collected).
- Startup generation parses the sample mission's `generate_startup.cmake`
  shape only.
- Topic IDs only from `<app>/fsw/inc/<app>_topicids.h`.
- `sb_highest_valid_msgid` does not follow a mission that replaces
  `cfe_sb_platform_cfg.h` wholesale.
- Validate sees declared MIDs only: md dwell packets use
  `MD_DWELL_PKT_MID_BASE + TblIndex` (`apps/md/fsw/src/md_app.c:205-208`).
- SBN MIDs have `class/scope: null`, so `mid-class-bit` and `mid-cross-cpu`
  skip them.

## Next

1. Rico reviews `worktree-mid-rules`; on approval: commit, push, PR.
2. Startup rules B-1 to B-3 (error), once Rico selects them.

## Awaiting approval

- Commit, push and PR of `worktree-mid-rules`.
- Implementation of B-1 to B-3.
- `.venv` creation and package installs; builds.
