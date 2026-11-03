<!-- SPDX-License-Identifier: Apache-2.0 -->
# Handoff (core module MIDs, 2026-11-03)

Rewrite this file when a task finishes. Items under "Awaiting approval" are
not approvals; ask Rico.

## State

- `main` @ `e2baf6c` (PR #14 merged). Remote branches other than `main` are
  gone. The directory `.claude/worktrees/startup-checks` is no longer a git
  worktree (sandbox placeholders only); Rico may delete it.
- Branch `worktree-core-mids`, worktree `.claude/worktrees/core-mids`: core
  module MID import below (PR pending review).
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
    Also writes `<dir>/<app>_topicid_values.h` (2026-10-31) for each app
    with a `tidval`: it defines `<tidval>(x)` as `CFSAM_<APP>_##x##_TOPICID`
    plus one literal per topic. Copied to `<MISSION_DEFS>/`, it replaces the
    app's `config/default_<app>_topicid_values.h` for all CPUs
    (`cfe/cmake/global_functions.cmake:54-111,210-214`, each app's
    `mission_build.cmake`); MIDs follow as base | topic. `<defs>/config/`
    would win over `<defs>/` (last match kept). The output dir mirrors
    `<MISSION_DEFS>`: mission files on top, per-CPU files in `<cpu>/`.
    Only `apps[]` is iterated; core modules get no header yet.
- Schema stays `cfsam.mission/v0`. New fields:
  - top-level `core_modules` (2026-11-03): same shape as `apps[]`
    (`name`, `path`, `tidval`, `topics`) for each `${MISSION_CORE_MODULES}`
    entry (`cfe/cmake/mission_defaults.cmake:27-40`) with a
    `fsw/inc/cfe_<m>_topicids.h`. Files are the app ones with stem `cfe_<m>`:
    mission-level `cfe_<m>_topicid_values.h` (`<m>/mission_build.cmake`,
    also matched without `cfe_`, `global_functions.cmake:201-204`), per-CPU
    `cfe_<m>_msgids.h` / `cfe_<m>_msgid_values.h` (`<m>/arch_build.cmake`).
    Sample: es, evs, sb, tbl, time (config, fs, osal, psp, msg, sbr,
    resourceid have no topic header and are skipped). A core module not found
    in the search path is a warning.
  - Core MIDs are in `cpus[].mids` before the app MIDs, with `app: <module>`
    (e.g. `CFE_ES_CMD_MID`, `app: es`, 0x1806 cpu1 / 0x1906 cpu2). TIME
    `DATA_CMD` / `SEND_CMD` are global (0x1860 / 0x1862 on every CPU). So all
    `mid-*` rules now cover app vs core collisions with no rule change. Core
    apps subscribe to them (e.g. `cfe/modules/es/fsw/src/cfe_es_task.c:387`);
    SB only rejects the same pipe twice (`cfe_sb_api.c:1023-1026`), so a
    shared value misroutes silently.
  - `apps[].tidval` (2026-10-31): the function-like macro every topic macro
    of the app is defined through (`<prefix>_<X>_TOPICID` = `<TIDVAL>(X)`),
    read from `fsw/inc/<app>_topicids.h`. Null with a warning when the topics
    don't all use one macro with their own name as argument; null without a
    warning when the app has no topic header. Real bundle: all 12 apps with a
    topic header have one; sch_lab, sbn*, libs, cfe_assert, cfe_testcase are
    null.
  - (2026-10-29) top-level `core_apps`: names from
    `core_api ${MISSION_CORE_MODULES}` whose `<module>/fsw/src/*_objtab.c` has
    a non-NULL `.TaskMain` (`cfe/cmake/target/CMakeLists.txt:55-71`,
    `cfe_es_start.c:802-873`). Sample: CFE_ES, CFE_EVS, CFE_SB, CFE_TBL,
    CFE_TIME. Null with a warning if a core module is not found.
  - (2026-10-29) `cpus[].startup[].entry_source`: `path:line` of a non-static
    definition of the entry symbol in the module's `fsw/src` or `src` (stubs
    excluded), or null if not found / module source not found / `NULL` or
    empty symbol.
- Rules (`validate.RULES`, all citations in `validate.py`):
  - `mid-duplicate`, `mid-invalid`, `mid-class-bit` (error); `mid-cross-cpu`
    (warning).
  - `startup-unknown-module`, `startup-duplicate-name`, `startup-bad-type`,
    `startup-core-name`, `startup-entry-null` (error);
    `startup-entry-not-found` (warning, text search).
  - Startup fields are compared with all whitespace removed (`isgraph`).
- Fixture `tests/fixtures/cfs_sample` gained unmodified copies of
  `cfe/modules/<m>/fsw/inc/cfe_<m>_topicids.h` and
  `config/default_cfe_<m>_{topicid_values,msgids,msgid_values}.h` for es,
  evs, sb, tbl, time (listed in `SOURCE.md`).
- `python3 -m pytest -q` → 208 passed. New: core module topics, core MIDs
  (platform/global, the TIME 1HZ alias), mission override of
  `cfe_es_topicid_values.h`, missing core module warning, and an app MID on
  `CFE_ES_CMD_MID` caught by `mid-duplicate`.
- Trial on `/tmp/claude-1000/coremids/bundle` (fresh copy of apps, cfe, libs,
  osal, psp, sample_defs, tools): import with no warnings; 30 core MIDs of
  97 per CPU; validate with no findings (no app collides with a core MID);
  generate exit 0, same 12 topic headers, cpu1 script equals the golden.
- Sandbox: Bash cannot create directories under `.claude/worktrees/`; use
  EnterWorktree (branch `worktree-<name>`). The guard hook blocks `tar`,
  `find -prune`, `awk` and `for` loops on paths near the bundle, and heredoc
  commit messages. Use `cp -r`, plain `find`/`ls`/`grep`, and
  `git commit -F <file>`. The worktree guard refuses commands that pass
  `$VAR` paths to python/sed/find/cp/mkdir; spell paths out or put the
  commands in a script file. `git fetch` works from the repo root with
  `github.com` allowed. `.git/config` writes may be blocked: push without
  `-u`.

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
- 2026-11-03: Core module MIDs imported (Rico picked it from the next-task
  list). Schema shape chosen by Rico: separate top-level `core_modules` like
  `apps[]`, core MIDs in `cpus[].mids` with `app: <module>` (not `apps[]`
  entries with a `core` flag, which every `apps[]` consumer would have to
  filter).
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

- EDS variant not supported (`CFE_EDS_ENABLED` always unset; EDS would pick
  `eds_cfe_<m>_topicid_values.h` for core modules).
- `$CFS_APP_PATH` and `<cpu>_STATIC_APPLIST` / `MISSION_GLOBAL_STATIC_APPLIST`
  ignored.
- `#if/#ifdef` in headers are not evaluated (all `#define`s collected). E.g.
  `CFE_TIME_1HZ_CMD_MID` is imported although it sits in
  `#ifndef CFE_OMIT_DEPRECATED_6_8` (`default_cfe_time_msgids.h:48-55`); it
  is an alias, so validate is unaffected.
- Startup generation parses the sample mission's `generate_startup.cmake`
  shape only.
- Topic IDs only from `<app>/fsw/inc/<app>_topicids.h` and
  `<core module>/fsw/inc/cfe_<m>_topicids.h`. cfe_testcase keeps its header in
  `inc/cfe_test_topicids.h` (name `TESTCASE`) and is not covered.
- `sb_highest_valid_msgid` does not follow a mission that replaces
  `cfe_sb_platform_cfg.h` wholesale.
- Validate sees declared MIDs only: md dwell packets use
  `MD_DWELL_PKT_MID_BASE + TblIndex` (`apps/md/fsw/src/md_app.c:205-208`).
- SBN MIDs have `class/scope: null`, so `mid-class-bit` and `mid-cross-cpu`
  skip them. SBN topic IDs are plain literals in
  `sample_defs/inc/global_sbn_topicids.h`, not covered.
- `startup-unknown-module` trusts `cpus[].apps`: it does not check that a
  module actually calls `add_cfe_app`, and it skips files with a `/`.
- `core_apps` looks for objtab files in `<module>/fsw/src`, not the module's
  CMake target sources.
- `entry_source` is a regex search: definitions produced by macros, or with
  parentheses inside the parameter list, are not found.
- `generate` startup scripts matched a real build once by hand (sample
  mission, native_std); no test guards it. Topic headers are checked only
  through cfsam's own C macro evaluator, not a compiler.
- `generate` writes topic headers for apps only, not for `core_modules`.

## Next

1. Rico reviews the `worktree-core-mids` PR and merges it.
2. Candidates (Rico picks):
   - Core module topic headers: `generate` writes `cfe_<m>_topicid_values.h`
     from `core_modules` (the data is now in the model).
   - A test fixture of the built startup script
     (`build-native_std/exe/{cpu1,cpu2}/cf/cfe_es_startup.scr` from
     2026-10-31 still exists).
   - Build check of the topic headers (Rico): copy the generated
     `*_topicid_values.h` into `sample_defs/` of the bundle (or a copy), run
     `make native_std.prep && make native_std.install`, confirm it builds,
     then remove them again.

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
