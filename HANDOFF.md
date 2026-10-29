<!-- SPDX-License-Identifier: Apache-2.0 -->
# Handoff (after PR #7, before startup rules, 2026-10-29)

Rewrite this file when a task finishes. Items under "Awaiting approval" are
not approvals; ask Rico.

## State

- `main` @ `41f5f74` (PR #7 merged: `mid-invalid`, `mid-class-bit`,
  `mid-cross-cpu`). Remote has only `main`; no other worktrees or branches
  besides this handoff branch.
- `src/cfsam/`: `cmake.py`, `cpp.py`, `importer.py`, `yamlout.py`,
  `validate.py`, `cli.py`. Commands: `cfsam import <bundle> [-o FILE]
  [--simulation] [--mission-config]`; `cfsam validate <mission.yaml>` →
  `severity: [rule] where: message`, exit 0 / 1 on errors / 2 on load error.
- Schema `cfsam.mission/v0`: `variant`, `mission`, `apps` (name, path,
  topics[name, topic_id]), `cpus` (name, processor_id, toolchain, platform,
  apps, mid_base, sb_highest_valid_msgid, mids[name, app, topic, class,
  scope, value], startup[type, file, entry, name, priority, stack, load_addr,
  exception_action]). Golden: `tests/golden/cfs_sample/mission.yaml`.
- Rules in `validate.RULES` (citations in the code):
  - `mid-duplicate` (error): two different messages on one CPU share a MID.
    Aliases with the same (app, topic, class, scope) pass
    (`SC_1HZ_WAKEUP_MID` = `SC_WAKEUP_MID`); `topic: null` MIDs count per name.
  - `mid-invalid` (error): MID is 0 or above `sb_highest_valid_msgid`.
  - `mid-class-bit` (error): cmd with bit 0x1000 clear / tlm with it set.
  - `mid-cross-cpu` (warning): same platform MID value on two or more CPUs.
- `python3 -m pytest -q` → 172 passed. PyYAML 6.0.3 comes from system Python
  (apt `python3-yaml`); no venv needed.
- Trial on a `$TMPDIR` copy of the real bundle: 19 apps, 67 MIDs per CPU,
  16 startup entries; import has no warnings; validate has no findings.
  Make the copy with `cp -r` of `apps cfe libs osal psp sample_defs tools`
  into `$TMPDIR/trial/bundle` (the guard hook blocks `tar`); `$TMPDIR` may
  have been cleaned.

## Next: startup rules (fact-checked, severity error, not yet approved to implement)

The importer writes the fixed `file(WRITE)` lines of
`sample_defs/generate_startup.cmake:17-24` unconditionally (cfe_assert,
sample_lib, sch_lab, ci_lab, to_lab, sample_app), then one templated line per
`CFS_APP_STARTUP_ORDER` app (`:27-36`) present in the CPU's app list
(`sample_defs/cpu1/install_custom.cmake:47-48`). cFE ES logs a bad line to
syslog and skips it; startup continues
(`cfe/modules/es/fsw/src/cfe_es_startupscript.c:296-300`), so the app is
silently missing.

- B-1 `startup-unknown-module` (error): a startup entry's `file` is not in
  the CPU's `apps`. ES: "Could not load file"
  (`cfe/modules/es/fsw/src/cfe_es_apps.c:167-176`). Sample: all six fixed
  modules are in both CPUs' lists (`sample_defs/targets.cmake:89-140`,
  `cfe/cmake/mission_defaults.cmake:109`), so no findings. Do not check the
  reverse: `cfe_testcase`, `sbn_udp`, `sbn_f_remap` are in the app list with no
  startup line, by design.
- B-2 `startup-duplicate-name` (error): two entries on one CPU share `name`,
  including app vs library. ES: `CFE_ES_ERR_DUPLICATE_NAME`
  (`cfe_es_apps.c:445-449` apps, `:623-631` libs; an app reusing a lib name
  fails in OSAL, `osal/src/os/shared/src/osapi-module.c:214`).
- B-3 `startup-bad-type` (error): `type` is not exactly `CFE_APP` or
  `CFE_LIB` ("Unexpected EntryType", `cfe_es_startupscript.c:362,406,415-418`).
- Not checkable from mission.yaml: entry point existence. Facts for later:
  load_addr is never read; priority is clamped; exception_action > 0 means
  restart (`cfe_es_startupscript.c:370-399`). The generated
  `/cf/cfe_es_startup.scr` is the only startup file used (no hand-written one
  under `sample_defs`).

Workflow: `add-validation-rule` skill (tests first in
`tests/test_validate.py`, golden mission.yaml as the passing case, edit the
model in the test for failing cases).

## Decisions

- 2026-10-28: Handoff via tracked `HANDOFF.md`, auto-loaded by `@HANDOFF.md`
  in CLAUDE.md; rewritten, not appended.
- 2026-10-28: Approvals relayed by `rico/cursor` count as Rico's own.
  2026-10-29: report and ask Rico in the terminal, not via cursor.
- 2026-10-29: Schema stays `cfsam.mission/v0` when fields are added.
  mission.yaml is written by stdlib `cfsam.yamlout`, read back with PyYAML.
- 2026-10-29: No topic-ID rule: MID = base | topic
  (`cfe/modules/core_api/config/default_cfe_core_api_msgid_mapping.h:49-86`)
  and no topic limit is documented, so rules check computed MID values.
- 2026-10-29: Startup rules B-1 to B-3 will be errors.
- Importer evaluates cFS build logic instead of hardcoding values; anything
  it cannot evaluate raises or becomes a warning, never a guess.
- Agents do not build the cFS bundle; Rico runs bundle builds. Merges,
  remote branch deletion, and removal of worktrees are done by Rico outside
  Claude Code.
- Fixtures are unmodified bundle copies at bundle-relative paths, listed in
  `tests/fixtures/cfs_sample/SOURCE.md`; tests never read the real bundle.

## Environment notes

- New worktree: use EnterWorktree (Bash cannot create directories under
  `.claude/worktrees/`). It names the branch `worktree-<name>` and starts
  from origin/main. If the session is already in a worktree, ExitWorktree
  (`keep`) first.
- After Rico removes the worktree this session is in, run ExitWorktree
  (`keep`) before using git from the main checkout.
- Guard hook false positives: heredoc commit messages (write the message to
  a `$TMPDIR` file, `git commit -F`), `tar` and `find -prune` on the bundle
  (use `cp -r`, plain `ls`/`grep`). `$TMPDIR` expansions next to
  `PYTHONPATH=src python3` are refused; use the literal `/tmp/claude-1000/...`.
- Network: pass `allowed_domains` `github.com` (push/fetch) and
  `api.github.com` (`gh`).
- Blocked even with approval: `gh pr merge`, `git push origin --delete`,
  `.git/config` writes (upstream tracking, branch config). Give Rico the
  commands to run outside Claude Code.
- Untracked sandbox placeholders (`.bashrc`, `.gitconfig`, `.mcp.json`,
  `.idea`, `.vscode`, `.claude/commands`, ...) appear in every worktree; never
  commit or gitignore them. Stage files by name.

## Limitations (v0)

- EDS variant not supported (`CFE_EDS_ENABLED` always unset).
- `$CFS_APP_PATH` and static app lists ignored; `#if/#ifdef` not evaluated.
- Startup generation parses the sample mission's `generate_startup.cmake`
  shape only.
- Topic IDs only from `<app>/fsw/inc/<app>_topicids.h`.
- `sb_highest_valid_msgid` does not follow a mission that replaces
  `cfe_sb_platform_cfg.h` wholesale.
- Validate sees declared MIDs only (md dwell packets use
  `MD_DWELL_PKT_MID_BASE + TblIndex`, `apps/md/fsw/src/md_app.c:205-208`).
- SBN MIDs have `class/scope: null`; `mid-class-bit` and `mid-cross-cpu`
  skip them.

## Awaiting approval

- Implementation of B-1 to B-3.
- `.venv` creation and package installs; builds.
