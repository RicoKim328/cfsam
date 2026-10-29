<!-- SPDX-License-Identifier: Apache-2.0 -->
# Handoff (validate stage started, 2026-10-29)

Rewrite this file when a task finishes. Items under "Awaiting approval" are
not approvals; ask Rico.

## State

- `main` @ `f5fa612` (PR #5 merged: post-MVP handoff).
- Branch `validate` (from `f5fa612`), worktree `.claude/worktrees/validate`:
  first validate stage, **uncommitted** (commit/push/PR not yet approved).
  Upstream tracking is unset (`.git/config` is protected).
- `src/cfsam/`: `cmake.py`, `cpp.py`, `importer.py`, `yamlout.py` as before;
  new `validate.py` (load mission.yaml with PyYAML, check `schema`, run
  `RULES`, return `Finding(severity, rule, where, message)`); `cli.py` adds
  `cfsam validate <mission.yaml>`: prints `error: [rule] where: message`,
  exit 0 (no errors) / 1 (errors) / 2 (load error).
- Rules: `mid-duplicate` (error): two different messages on one CPU share a
  MID value. Messages are identified by (app, topic, class, scope), so
  aliases such as `SC_1HZ_WAKEUP_MID` = `SC_WAKEUP_MID`
  (`apps/sc/config/default_sc_msgids.h:50`) pass; MIDs with `topic: null`
  (SBN) count per name.
- `pyproject.toml`: `dependencies = ["PyYAML>=6"]`. PyYAML 6.0.3 is already
  in system Python (apt `python3-yaml`); nothing was installed.
- `python3 -m pytest -q` → 162 passed (`tests/test_validate.py`: 11).
- Trial on a `$TMPDIR` copy of the real bundle (apps, cfe, libs, osal, psp,
  sample_defs, tools copied with `cp -r`; the guard hook blocks `tar`):
  import, then validate → no findings, exit 0. Before the alias handling it
  reported SC_WAKEUP/SC_1HZ_WAKEUP on both CPUs.
- Worktrees: `validate` (current), `mvp` (branch `handoff-post-mvp`, merged,
  removable), `harness` (merged). Remote branches `handoff-post-mvp` and
  `handoff-post-merge` are merged and can be deleted.
- Sandbox: Bash cannot create directories under `.claude/worktrees/`; create
  worktrees with EnterWorktree (it names the branch `worktree-<name>`; switch
  to the wanted branch and delete the generated one).

## Decisions

- 2026-10-28: Handoff via tracked `HANDOFF.md`, auto-loaded by `@HANDOFF.md`
  in CLAUDE.md; rewritten, not appended.
- 2026-10-28: Approvals relayed by `rico/cursor` count as Rico's own.
- 2026-10-29: Schema `cfsam.mission/v0`. mission.yaml is written by stdlib
  `cfsam.yamlout` and read back with PyYAML (approved 2026-10-29).
- 2026-10-29: `topic-id-collision` dropped. Fact-check: MID = base | topic
  (`cfe/modules/core_api/config/default_cfe_core_api_msgid_mapping.h:49-86`),
  and the OR makes collisions possible across scopes (cpu1 platform topic
  0x60-0x7F vs global 0x1860 base), so `mid-duplicate` on computed values is
  the authoritative check and a topic-ID rule would be a weaker subset.
- 2026-10-29: `mid-duplicate` is an error: SB keys routes by MsgId only and
  delivers to every subscriber with no ownership check
  (`cfe/modules/sb/fsw/src/cfe_sb_api.c:989-1058`,
  `cfe/modules/sb/fsw/src/cfe_sb_priv.c:1052-1069`).
- Importer evaluates cFS build logic instead of hardcoding values; anything
  it cannot evaluate raises or becomes a warning, never a guess.
- The guard hook blocks running cfsam on `../`; trial imports use a copy in
  `$TMPDIR`.
- Agents do not build the cFS bundle; Rico runs bundle builds. Merges and
  remote branch deletion are done by Rico.
- Fixtures are unmodified bundle copies at bundle-relative paths; tests never
  read the real bundle. Golden snapshots live in `tests/golden/`. Validate
  tests use the golden mission.yaml as the passing case and edit it in the
  test for failing cases.

## Limitations (v0)

- EDS variant not supported (`CFE_EDS_ENABLED` always unset).
- `$CFS_APP_PATH` and `<cpu>_STATIC_APPLIST` / `MISSION_GLOBAL_STATIC_APPLIST`
  ignored.
- `#if/#ifdef` in headers are not evaluated (all `#define`s collected).
- Startup generation parses the sample mission's `generate_startup.cmake`
  shape only.
- Topic IDs only from `<app>/fsw/inc/<app>_topicids.h`.
- Validate sees declared MIDs only: md dwell packets use
  `MD_DWELL_PKT_MID_BASE + TblIndex` (`apps/md/fsw/src/md_app.c:205-208`),
  values not in mission.yaml.
- Validate is per CPU; a mission-wide (SBN) rule must exempt `scope: global`
  (TIME `0x1860`/`0x1862` are the same on all CPUs by design).

## Next

1. Rico reviews the `validate` branch; on approval: commit, push, PR.
2. Further rule candidates (fact-check first): topic ID range so `base | topic`
   cannot reach another CPU's base or the other class (cpu1 topic ≥ 0x100
   equals cpu2's base; ≥ 0x800 flips class); startup entries naming apps not
   in the CPU's app list.
3. Rico (outside Claude Code): remove merged worktrees `mvp`, `harness`,
   `init-claude-md` and their branches; delete remote `handoff-post-mvp`,
   `handoff-post-merge`, `worktree-init-claude-md`.

## Awaiting approval

- Commit, push and PR of the `validate` branch.
- `.venv` creation and package installs; builds.
