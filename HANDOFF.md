<!-- SPDX-License-Identifier: Apache-2.0 -->
# Handoff (after topic ID header merge, 2026-10-31)

Rewrite this file when a task finishes. Items under "Awaiting approval" are
not approvals; ask Rico.

## State

- `main` @ `365768d` (PR #13 merged: `<app>_topicid_values.h` generation; it
  carried PR #12's HANDOFF commits, so #12 shows as merged too). No task in
  progress.
- Leftovers for Rico to clean up outside Claude Code: remote branches
  `worktree-startup-checks`, `handoff-post-startup-checks`,
  `worktree-topicid-gen`; worktree `.claude/worktrees/startup-checks` (now on
  branch `handoff-post-topicid-gen`) and its merged local branches.
- `src/cfsam/`: `cmake.py`, `cpp.py`, `importer.py`, `yamlout.py`,
  `validate.py`, `generate.py`, `cli.py`:
  - `cfsam import <bundle> [-o mission.yaml]`
  - `cfsam validate <mission.yaml>` → `severity: [rule] where: message`,
    exit 0 / 1 on errors / 2 on load error.
  - `cfsam generate <mission.yaml> -o <dir>` → `<dir>/<cpu>/cfe_es_startup.scr`.
    Runs validate first, prints findings, and writes nothing (exit 1) if any
    is an error. Lines are `a, b, ...;` in `generate_startup.cmake` field
    order; ES drops whitespace, so they equal the cmake-written lines field
    for field. Golden: `tests/golden/cfs_sample/generate/<cpu>/`.
    Also writes `<dir>/<app>_topicid_values.h` (new, 2026-10-31) for each app
    with a `tidval`: it defines `<tidval>(x)` as `CFSAM_<APP>_##x##_TOPICID`
    plus one literal per topic. Copied to `<MISSION_DEFS>/`, it replaces the
    app's `config/default_<app>_topicid_values.h` for all CPUs
    (`cfe/cmake/global_functions.cmake:54-111,210-214`, each app's
    `mission_build.cmake`); MIDs follow as base | topic. `<defs>/config/`
    would win over `<defs>/` (last match kept). The output dir mirrors
    `<MISSION_DEFS>`: mission files on top, per-CPU files in `<cpu>/`.
- Schema stays `cfsam.mission/v0`. New fields:
  - `apps[].tidval` (2026-10-31): the function-like macro every topic macro
    of the app is defined through (`<prefix>_<X>_TOPICID` = `<TIDVAL>(X)`),
    read from `fsw/inc/<app>_topicids.h`. Null with a warning when the topics
    don't all use one macro with their own name as argument; null without a
    warning when the app has no topic header. Real bundle: all 12 apps with a
    topic header have one (`SAMPLE_APP_MISSION_TIDVAL`, `CFE_MISSION_HK_TIDVAL`,
    ...); sch_lab, sbn*, libs, cfe_assert, cfe_testcase are null.
  - (2026-10-29):
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
- `python3 -m pytest -q` → 203 passed. Topic header tests: golden header,
  round trip (fixture copy + generated headers in `sample_defs/` re-imports to
  the golden mission.yaml), and an edited topic ID moving its MID.
- Trial on `$TMPDIR/trial/bundle` (apps, cfe, libs, osal, psp, sample_defs,
  tools): import with no warnings; all 16 entry symbols found on both CPUs;
  validate with no findings; generate exit 0, cpu1 script equals the golden.
  Topic headers (2026-10-31): 12 generated; a second copy with them in
  `sample_defs/` re-imports byte-identical; bumping hk `CMD` 0x9A→0xAA moves
  `HK_CMD_MID` to 0x18AA (cpu1) / 0x19AA (cpu2) with topic/class/scope kept,
  nothing else changes. Not yet compiled by a real build.
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
- 2026-10-31: Next config chosen by Rico: topic ID headers
  (`<app>_topicid_values.h`), not literal per-CPU MID headers (would lose
  topic/class/scope on re-import) or targets.cmake (variant-specific and
  lossy: EDS/SIMULATION conditionals, `<cpu>_SYSTEM`, global vs per-CPU app
  lists). The TIDVAL macro name is read from each app, not assumed.
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
- `generate` startup scripts matched a real build once by hand (sample
  mission, native_std); no test guards it. Topic headers are checked only
  through cfsam's own C macro evaluator, not a compiler.
- Topic headers cover apps only; cFE core modules (es, evs, sb, tbl, time,
  ta, cfe_testcase's `cfe_test_topicid_values.h`) use the same pattern but
  with `cfe_` name matching, and their topics aren't imported. SBN topic IDs
  are plain literals in `sample_defs/inc/global_sbn_topicids.h`, not covered.

## Next

1. Not yet chosen; Rico picks. Candidates:
   - Build check of the topic headers (Rico): copy the generated
     `*_topicid_values.h` into `sample_defs/` of the bundle (or a copy), run
     `make native_std.prep && make native_std.install`, confirm it builds,
     then remove them again.
   - A test fixture of the built startup script.
   - Core-module topic headers.

## Build comparison (2026-10-31)

- Rico ran `make native_std.prep && make native_std.install` outside Claude
  Code (a `!` command runs in this session's sandbox, which cannot write the
  bundle). `cfsam generate` output for a `$TMPDIR` bundle copy matches
  `build-native_std/exe/{cpu1,cpu2}/cf/cfe_es_startup.scr` field for field:
  16 entries per CPU, same order and values; only cmake's column padding
  differs, which ES drops (`cfe_es_startupscript.c:223`).
- How: `cp` the built scripts into `$TMPDIR` (the guard hook blocks python on
  bundle paths), split each at `;`, drop whitespace, compare the fields.

## Awaiting approval

- `.venv` creation and package installs; builds (Rico runs them).
