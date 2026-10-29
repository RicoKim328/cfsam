<!-- SPDX-License-Identifier: Apache-2.0 -->
# Handoff (after startup rules merge, 2026-10-29)

Rewrite this file when a task finishes. Items under "Awaiting approval" are
not approvals; ask Rico.

## State

- `main` @ `5438bab` (PR #9 merged: `startup-unknown-module`,
  `startup-duplicate-name`, `startup-bad-type`). No task in progress.
- Leftovers for Rico to clean up outside Claude Code: remote branch
  `worktree-startup-rules`, worktree `.claude/worktrees/startup-rules`
  (now on branch `handoff-post-startup-rules`), and a stale
  `.git/config.lock` that blocks git config writes (branch upstream setup).
- `src/cfsam/`: `cmake.py`, `cpp.py`, `importer.py`, `yamlout.py`,
  `validate.py`, `cli.py` (`cfsam import`, `cfsam validate <mission.yaml>`
  → `severity: [rule] where: message`, exit 0 / 1 on errors / 2 on load
  error).
- Schema stays `cfsam.mission/v0`, including
  `cpus[].sb_highest_valid_msgid`. The importer evaluates it from
  `cfe/modules/sb/fsw/inc/cfe_sb_internal_cfg.h:155-156` and the per-CPU
  `cfe_sb_internal_cfg_values.h`. If it cannot, it warns and writes null.
- Rules (`validate.RULES`, all citations in `validate.py`):
  - `mid-duplicate` (error): two different messages on one CPU share a MID.
    Aliases with the same (app, topic, class, scope) pass.
  - `mid-invalid` (error): MID is 0 or above `sb_highest_valid_msgid`.
  - `mid-class-bit` (error): the cmd/tlm class disagrees with bit 0x1000.
  - `mid-cross-cpu` (warning): the same platform MID value on two or more CPUs.
  - `startup-unknown-module` (error): the startup `file` module (the part
    before the first `.`) is not in the CPU's `apps`. Files containing `/` are
    skipped, because ES then drops the `/cf` prefix (`cfe_fs_api.c:470-540`).
  - `startup-duplicate-name` (error): two startup entries on one CPU have the
    same `name`. Apps and libs share the namespace; matching is
    case-sensitive.
  - `startup-bad-type` (error): `type` is not exactly `CFE_APP`/`CFE_LIB`.
  - Startup fields are compared as ES reads them, with all whitespace removed
    (`isgraph`, `cfe_es_startupscript.c:223`).
- `python3 -m pytest -q` → 181 passed.
- Trial on a `$TMPDIR/trial/bundle` copy (apps, cfe, libs, osal, psp,
  sample_defs, tools): import with no warnings, validate with no findings,
  exit 0.
- Sandbox: Bash cannot create directories under `.claude/worktrees/`; use
  EnterWorktree (branch `worktree-<name>`). The guard hook blocks `tar`,
  `find -prune` and `awk` on paths near the bundle, and heredoc commit
  messages. Use `cp -r`, plain `find`/`ls`/`grep`, and `git commit -F <file>`.
  The worktree guard refuses commands that pass `$VAR` paths to python/sed;
  spell paths out.

## Decisions

- 2026-10-28: Handoff via tracked `HANDOFF.md`, auto-loaded by `@HANDOFF.md`
  in CLAUDE.md; rewritten, not appended.
- 2026-10-28: Approvals relayed by `rico/cursor` count as Rico's own.
- 2026-10-29: Schema `cfsam.mission/v0`, written by stdlib `cfsam.yamlout`,
  read back with PyYAML. Adding fields keeps v0.
- 2026-10-29: No topic-ID rule. MID = base | topic
  (`cfe/modules/core_api/config/default_cfe_core_api_msgid_mapping.h:49-86`),
  so rules check computed MID values.
- 2026-10-29: Severities: `mid-*` errors except `mid-cross-cpu` (warning, only
  matters when CPUs share a bus). Startup rules are errors: ES logs a bad line,
  skips it and keeps booting without that module
  (`cfe/modules/es/fsw/src/cfe_es_startupscript.c:296-302`).
- 2026-10-29: B-1 to B-3 implemented on Rico's "다음 작업 실행". Fact-check
  corrections applied: a duplicate lib returns `CFE_ES_ERR_DUPLICATE_NAME`, not
  `CFE_ES_LIB_ALREADY_LOADED` (unused in this bundle). `.` and `/` in a file
  name each turn off only the default extension and only the `/cf` prefix,
  respectively.
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
- `startup-unknown-module` trusts `cpus[].apps`: it does not check that a
  module actually calls `add_cfe_app`, and it skips files with a `/`.
- `startup-duplicate-name` does not check against the core app names
  (CFE_ES, CFE_EVS, ...), which share the ES AppTable.

## Next

1. Not yet chosen; Rico picks. Candidates: core-app name clash for startup
   names (CFE_ES, CFE_EVS, ...); startup `entry` symbol checks; config
   generation.

## Awaiting approval

- The next task's selection.
- `.venv` creation and package installs; builds.
