<!-- SPDX-License-Identifier: Apache-2.0 -->
# Handoff (MVP importer, 2026-10-29)

Rewrite this file when a task finishes. Items under "Awaiting approval" are
not approvals; ask Rico.

## State

- `main` @ `593a1d1` (PR #3 merged: post-harness HANDOFF update; PR #2
  harness merged before it). MVP importer is on branch `worktree-mvp`
  (worktree `.claude/worktrees/mvp`), pushed; PR #4
  (https://github.com/RicoKim328/cfsam/pull/4) open, `origin/main` merged in to
  resolve the HANDOFF.md conflict. Local upstream tracking for `worktree-mvp`
  is not set (`.git/config` is sandbox-protected).
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
- `python3 -m pytest -q` → 151 passed (103 harness + 48 new), system Python
  3.10, no venv needed.
- Trial import of a copy of the real bundle (apps/, libs/, sample_defs/,
  cfe/cmake, cfe/modules/{core_api,cfe_assert,cfe_testcase} under `$TMPDIR`):
  19 apps found, 67 MIDs per CPU, 16 startup entries; topic IDs for 12 apps.
  The 6 SBN MIDs have `class/topic: null` because sample_defs/<cpu>/sbn_msgids.h
  adds the CPU base directly instead of using the mapping macros.
- cFS facts in `importer.py` were checked with `cfs-fact-checker` (9 claims:
  8 confirmed, 1 partial → limitations below).
- Codex stop-time review gate is on for the cfsam main checkout, `harness` and
  `init-claude-md` workspaces; not set for the `mvp` worktree.
- Housekeeping (from PR #3): branch `harness` deleted (local and remote); its
  stale `[branch "harness"]` section stays in `.git/config`. Not yet removed
  (Rico, outside Claude Code): the `init-claude-md` worktree, local branch
  `worktree-init-claude-md` and its remote; all merged and clean. Worktree
  directory `.claude/worktrees/harness` remains on branch
  `handoff-post-merge`. The local `main` checkout is behind `origin/main`;
  Rico pulls it.
- `.venv` exists only in the `harness` worktree (made with user-installed
  `virtualenv`; system `python3 -m venv` lacks ensurepip): ruamel.yaml 0.19.1,
  pytest 9.1.1. A new worktree needs its own (`python3 -m virtualenv .venv`).
- Bash sandbox (`enabled`, `failIfUnavailable`, `allowUnsandboxedCommands:
  false`) verified 2026-10-28: writes outside the worktree and `$TMPDIR`
  (`/tmp/claude-1000`) fail. `!` commands run in the same sandbox. Edit/Write
  are not sandboxed (the guard hook covers them).
- Sandbox placeholders (`.bashrc`, `.gitconfig`, `.mcp.json`, `.idea`,
  `.vscode`, `.claude/commands`, ...) and `.DS_Store`/`._.DS_Store` show as
  untracked; never commit or gitignore them. Stage files by name.
- Guard hook (secondary layer) is a best-effort allowlist parser: Bash touching
  the bundle must be read-only or a plain copy out of it; it also blocks bundle
  builds. Known false positives: `$NAME` words inside heredoc bodies and
  parentheses in `sed` expressions; use a file / the Edit tool instead.

## Decisions

- 2026-10-28: Handoff via tracked `HANDOFF.md`, auto-loaded by `@HANDOFF.md`
  in CLAUDE.md; rewritten, not appended.
- 2026-10-28: Approvals relayed by `rico/cursor` count as Rico's own. Rico
  (via cursor): "이제 MVP 구현하자" → MVP implementation approved.
- 2026-10-29: Rico (via cursor) accepted schema v0 and dropping `ruamel.yaml`
  (mission.yaml written by stdlib `cfsam.yamlout`; add a YAML library when
  mission.yaml is read back); approved commit, non-force push of
  `worktree-mvp` and PR #4. Rico merges PRs himself.
- 2026-10-29: Rico approved resolving the PR #4 HANDOFF.md conflict by merging
  `origin/main` into `worktree-mvp` and pushing.
- Importer evaluates cFS build logic (CMake subset, header override search,
  macro expansion) instead of hardcoding values; anything it cannot evaluate
  raises or becomes a warning, never a guess.
- The guard hook blocks running cfsam on `../`; trial imports use a copy in
  `$TMPDIR`.
- 2026-10-28: Agents do not build the cFS bundle; Rico runs bundle builds
  with `! make ...`. Merges and remote branch deletion are done by Rico
  outside Claude Code (the auto-mode classifier denies them to agents).
- 2026-10-28: Bundle write protection is Claude Code's Bash sandbox; the guard
  hook stays as a secondary layer. The bundle is not in `denyWrite`.
- Fixtures are unmodified bundle copies at bundle-relative paths; tests never
  read the real bundle. Golden snapshots live in `tests/golden/`.

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

1. Rico merges PR #4.
2. Rico (outside Claude Code): `git worktree remove .claude/worktrees/init-claude-md`,
   `git branch -d worktree-init-claude-md`, `git push origin --delete worktree-init-claude-md`.
3. Validate stage: read mission.yaml back (pick a YAML library; needs install
   approval / `.venv`), first rules via `add-validation-rule` (e.g. duplicate
   MID per CPU; same-class topic ID collision).

## Awaiting approval

- `.venv` creation and package installs; builds.
- Validate stage implementation.
