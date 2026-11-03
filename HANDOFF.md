<!-- SPDX-License-Identifier: Apache-2.0 -->
# Handoff (after core module topic header merge, 2026-11-03)

Rewrite this file when a task finishes. Items under "Awaiting approval" are
not approvals; ask Rico.

## State

- `main` @ `c569847` (PR #17 merged: `generate` writes core module topic ID
  headers). No task in progress.
- Leftovers for Rico to clean up outside Claude Code: remote branch
  `worktree-core-topicid-gen`; worktree `.claude/worktrees/core-topicid-gen`
  (now on branch `handoff-post-core-topicid-gen`) and the merged local
  branch `worktree-core-topicid-gen`.
- `src/cfsam/`: `cmake.py`, `cpp.py`, `importer.py`, `yamlout.py`,
  `validate.py`, `generate.py`, `cli.py`:
  - `cfsam import <bundle> [-o mission.yaml]`
  - `cfsam validate <mission.yaml>` → `severity: [rule] where: message`,
    exit 0 / 1 on errors / 2 on load error.
  - `cfsam generate <mission.yaml> -o <dir>` runs validate first, prints
    findings, and writes nothing (exit 1) if any is an error. Output mirrors
    `<MISSION_DEFS>`: mission files on top, per-CPU files in `<cpu>/`.
    - `<dir>/<cpu>/cfe_es_startup.scr`: lines `a, b, ...;` in
      `generate_startup.cmake` field order; ES drops whitespace, so they equal
      the cmake-written lines field for field.
    - `<dir>/<app>_topicid_values.h` for each app with a `tidval`, and
      (2026-11-03) `<dir>/cfe_<m>_topicid_values.h` for each `core_modules`
      entry with a `tidval` (sample: es, evs, sb, tbl, time). Each defines
      `<tidval>(x)` as `CFSAM_<STEM>_##x##_TOPICID` plus one literal per
      topic, where STEM is the app name or `cfe_<m>` (e.g.
      `CFSAM_CFE_ES_CMD_TOPICID`). Copied to `<MISSION_DEFS>/`, it replaces
      `<path>/config/default_<stem>_topicid_values.h` for all CPUs
      (`cfe/cmake/global_functions.cmake:54-111,196-214`, each module's
      `mission_build.cmake`); MIDs follow as base | topic. For `cfe_*` files
      `<defs>/` is also searched for `<m>_...` and `<MISSIONCONFIG>_<m>_...`;
      `cfe_<m>_...` is the last candidate there, so it wins. Files in
      `<defs>/config/` or `<defs>/cfe/` would still win over `<defs>/`
      (last match kept, `:111`).
    - Goldens: `tests/golden/cfs_sample/generate/`.
- Schema stays `cfsam.mission/v0`. Fields added since v0 started:
  - top-level `core_modules` (2026-11-03): same shape as `apps[]`
    (`name`, `path`, `tidval`, `topics`) for each `${MISSION_CORE_MODULES}`
    entry (`cfe/cmake/mission_defaults.cmake:27-40`) with a
    `fsw/inc/cfe_<m>_topicids.h`. Files are the app ones with stem `cfe_<m>`:
    mission-level `cfe_<m>_topicid_values.h`, per-CPU `cfe_<m>_msgids.h` /
    `cfe_<m>_msgid_values.h` (`<m>/arch_build.cmake`). Config, fs, osal,
    psp, msg, sbr, resourceid have no topic header and are skipped. A core
    module not found in the search path is a warning.
  - Core MIDs are in `cpus[].mids` before the app MIDs, with `app: <module>`
    (e.g. `CFE_ES_CMD_MID`, `app: es`, 0x1806 cpu1 / 0x1906 cpu2). TIME
    `DATA_CMD` / `SEND_CMD` are global (0x1860 / 0x1862 on every CPU). All
    `mid-*` rules cover app vs core collisions.
  - `apps[].tidval` (2026-10-31): the function-like macro every topic macro
    is defined through, read from `fsw/inc/<app>_topicids.h`. Null with a
    warning when the topics don't all use one macro with their own name as
    argument; null without a warning when there is no topic header. Real
    bundle: 12 apps have one; sch_lab, sbn*, libs, cfe_assert, cfe_testcase
    are null.
  - top-level `core_apps` (2026-10-29): names from
    `core_api ${MISSION_CORE_MODULES}` whose `<module>/fsw/src/*_objtab.c` has
    a non-NULL `.TaskMain` (`cfe/cmake/target/CMakeLists.txt:55-71`,
    `cfe_es_start.c:802-873`).
  - `cpus[].startup[].entry_source` (2026-10-29): `path:line` of a non-static
    definition of the entry symbol in the module's `fsw/src` or `src` (stubs
    excluded), or null.
- Rules (`validate.RULES`, all citations in `validate.py`):
  - `mid-duplicate`, `mid-invalid`, `mid-class-bit` (error); `mid-cross-cpu`
    (warning).
  - `startup-unknown-module`, `startup-duplicate-name`, `startup-bad-type`,
    `startup-core-name`, `startup-entry-null` (error);
    `startup-entry-not-found` (warning, text search).
  - Startup fields are compared with all whitespace removed (`isgraph`).
- `python3 -m pytest -q` → 215 passed. New (2026-11-03): goldens of the 5
  core headers, the CLI file list (8 files), editing the ES `CMD` topic moves
  `CFE_ES_CMD_MID` to 0x183F cpu1 / 0x193F cpu2 after re-import, and
  core modules without `tidval` are skipped. The existing round-trip test
  (write all headers into a fixture copy, re-import, equal golden
  mission.yaml) now covers the core headers too.
- Trial on `/tmp/claude-1000/coretidgen/bundle` (fresh copy of apps, cfe,
  libs, osal, psp, sample_defs, tools; script `trial.sh` next to it): import
  with no warnings, validate with no findings, generate exit 0 with 17
  headers (12 apps + 5 core), cpu1 script equals the golden. With the 17
  headers copied into its `sample_defs/`, re-import is byte-identical; 30
  core MIDs of 97 per CPU. Every `CFE_MISSION_<M>_TIDVAL(X)` use in the
  bundle's es/evs/sb/tbl/time headers (29) has a generated define (`ta` and
  `testcase` uses exist but those modules are not in the sample mission).
- Sandbox: Bash cannot create directories under `.claude/worktrees/`; use
  EnterWorktree (branch `worktree-<name>`). The guard hook blocks `tar`,
  `find -prune`, `awk`, `for` loops and relative-path `cp` on paths near the
  bundle, `sed -i` inside worktrees, and heredoc commit messages. Use the
  Edit tool, `cp -r` with absolute bundle paths, plain `find`/`ls`/`grep`,
  and `git commit -F <file>`. The worktree guard refuses commands that pass
  `$VAR` paths to python/sed/find/cp/mkdir or chain many steps; spell paths
  out or put the commands in a script file. `git fetch`/`push` work with
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
- 2026-10-29: Core app names are derived from objtab files, not hardcoded.
- 2026-10-29: Config generation scope chosen by Rico: per-CPU startup
  script first. Generate refuses on validate errors.
- 2026-10-31: Next config chosen by Rico: topic ID headers, not literal
  per-CPU MID headers (would lose topic/class/scope on re-import) or
  targets.cmake (variant-specific and lossy). The TIDVAL macro name is read
  from each module, not assumed.
- 2026-11-03: Core module MIDs imported; schema shape chosen by Rico:
  separate top-level `core_modules`, core MIDs in `cpus[].mids` with
  `app: <module>`.
- 2026-11-03: Core module topic headers (Rico approved the plan; PR #17,
  reviewed and merged by Rico). Written
  as `cfe_<m>_topicid_values.h` (the module's own config name, highest
  priority in `<defs>/`); literal macros prefixed `CFSAM_CFE_<M>_` (file
  stem, so no clash with an app named like a core module).
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
  `eds_cfe_<m>_topicid_values.h` as the core module fallback).
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
  mission, native_std); no test guards it. Topic headers (app and core) are
  checked only through cfsam's own C macro evaluator, not a compiler.
- A generated header in `<MISSION_DEFS>/` loses to an existing override of
  the same file in `<defs>/config/` or `<defs>/cfe/`; generate does not warn.

## Next

1. Build check of the topic headers (Rico): copy the 17 generated
   `*_topicid_values.h` (e.g. `/tmp/claude-1000/coretidgen/out/`, or rerun
   `cfsam generate`) into `sample_defs/` of the bundle (or a copy), run
   `make native_std.prep && make native_std.install`, confirm it builds and
   the "Using file:" lines name the copied headers, then remove them again.
2. Not yet chosen; Rico picks. Candidates:
   - A test fixture of the built startup script
     (`build-native_std/exe/{cpu1,cpu2}/cf/cfe_es_startup.scr` from
     2026-10-31 still exists).
   - Warn in `generate`/`validate` when the mission already has an override
     that would shadow a generated header.

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
