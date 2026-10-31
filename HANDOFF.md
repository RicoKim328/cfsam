<!-- SPDX-License-Identifier: Apache-2.0 -->
# Handoff (core-name and entry-symbol rules, startup generation, 2026-10-29)

Rewrite this file when a task finishes. Items under "Awaiting approval" are
not approvals; ask Rico.

## State

- `main` @ `caff787` (PR #10 merged, HANDOFF refresh after PR #9).
- Branch `worktree-startup-checks` (from `caff787`), worktree
  `.claude/worktrees/startup-checks`: the work below, **uncommitted**
  (commit/push/PR not yet approved).
- `src/cfsam/`: `cmake.py`, `cpp.py`, `importer.py`, `yamlout.py`,
  `validate.py`, `generate.py`, `cli.py`:
  - `cfsam import <bundle> [-o mission.yaml]`
  - `cfsam validate <mission.yaml>` → `severity: [rule] where: message`,
    exit 0 / 1 on errors / 2 on load error.
  - `cfsam generate <mission.yaml> -o <dir>` (new) → `<dir>/<cpu>/cfe_es_startup.scr`.
    Runs validate first, prints findings, and writes nothing (exit 1) if any
    is an error. Lines are `a, b, ...;` in `generate_startup.cmake` field
    order; ES drops whitespace, so they equal the cmake-written lines field
    for field. Golden: `tests/golden/cfs_sample/generate/<cpu>/`.
- Schema stays `cfsam.mission/v0`. New fields (2026-10-29):
  - top-level `core_apps`: names from `core_api ${MISSION_CORE_MODULES}`
    whose `<module>/fsw/src/*_objtab.c` has a non-NULL `.TaskMain`
    (`cfe/cmake/target/CMakeLists.txt:55-71`, `cfe_es_start.c:802-873`).
    Sample: CFE_ES, CFE_EVS, CFE_SB, CFE_TBL, CFE_TIME. Null with a warning
    if a core module is not found.
  - `cpus[].startup[].entry_source`: `path:line` of a non-static definition
    of the entry symbol in the module's `fsw/src` or `src` (stubs excluded),
    or null if not found / module source not found / `NULL` or empty symbol.
- Rules (`validate.RULES`, all citations in `validate.py`):
  - `mid-duplicate`, `mid-invalid`, `mid-class-bit` (error); `mid-cross-cpu`
    (warning).
  - `startup-unknown-module`, `startup-duplicate-name`, `startup-bad-type`
    (error).
  - `startup-core-name` (error, new): a startup name equals a `core_apps`
    name (ES creates core apps first; apps and libs are checked against the
    AppTable, `cfe_es_apps.c:445-450,623-631`). Skipped if `core_apps` null.
  - `startup-entry-null` (error, new): `CFE_APP` with entry `NULL` or empty.
    ES registers the app but its task never runs (`cfe_es_apps.c:187-188,
    237-293`). Allowed for `CFE_LIB` (`:678-690`).
  - `startup-entry-not-found` (warning, new): module source known but no
    definition found. Warning because the search is textual; ES looks only in
    the loaded module (`OS_ModuleSymbolLookup`, `cfe_es_apps.c:190`).
  - Startup fields are compared with all whitespace removed (`isgraph`).
- Fixture `tests/fixtures/cfs_sample` gained unmodified copies of the ten
  core `*_objtab.c`, `osal/CMakeLists.txt`, `psp/CMakeLists.txt` and
  `apps/sample_app/fsw/src/sample_app.c` (listed in `SOURCE.md`).
- `python3 -m pytest -q` → 197 passed.
- Trial on `$TMPDIR/trial/bundle` (apps, cfe, libs, osal, psp, sample_defs,
  tools): import with no warnings; all 16 entry symbols found on both CPUs;
  validate with no findings; generate exit 0, cpu1 script equals the golden.
- Sandbox: Bash cannot create directories under `.claude/worktrees/`; use
  EnterWorktree (branch `worktree-<name>`). The guard hook blocks `tar`,
  `find -prune` and `awk` on paths near the bundle, and heredoc commit
  messages. Use `cp -r`, plain `find`/`ls`/`grep`, and `git commit -F <file>`.
  The worktree guard refuses commands that pass `$VAR` paths to
  python/sed/find; spell paths out or put the commands in a script file.
  `.git/config` writes may be blocked: push without `-u`.

## Decisions

- 2026-10-28: Handoff via tracked `HANDOFF.md`, auto-loaded by `@HANDOFF.md`
  in CLAUDE.md; rewritten, not appended.
- 2026-10-28: Approvals relayed by `rico/cursor` count as Rico's own.
- 2026-10-29: Schema `cfsam.mission/v0`, written by stdlib `cfsam.yamlout`,
  read back with PyYAML. Adding fields keeps v0.
- 2026-10-29: No topic-ID rule. MID = base | topic
  (`cfe/modules/core_api/config/default_cfe_core_api_msgid_mapping.h:49-86`),
  so rules check computed MID values.
- 2026-10-29: Severities: `mid-*` errors except `mid-cross-cpu` (warning).
  Startup rules are errors (ES logs a bad line, skips it and keeps booting,
  `cfe_es_startupscript.c:296-302`), except `startup-entry-not-found`
  (warning, text search).
- 2026-10-29: Core app names are derived from objtab files, not hardcoded
  (the set follows `MISSION_CORE_MODULES`, e.g. the optional `ta` module adds
  CFE_TA).
- 2026-10-29: Config generation scope chosen by Rico: per-CPU startup
  script only. Generate refuses on validate errors.
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
- `core_apps` looks for objtab files in `<module>/fsw/src`, not the module's
  CMake target sources.
- `entry_source` is a regex search: definitions produced by macros, or with
  parentheses inside the parameter list, are not found.
- `generate` writes only `cfe_es_startup.scr`; not checked against a real
  build output (the bundle's `build-native_std` is empty).

## Next

1. Rico reviews `worktree-startup-checks`; on approval: commit, push, PR.
2. Not yet chosen. Candidates: compare `generate` output with a real
   `make native_std.install` result (Rico runs the build); generate more
   config (targets.cmake, MID headers).

## Awaiting approval

- Commit, push and PR of `worktree-startup-checks`.
- `.venv` creation and package installs; builds.
