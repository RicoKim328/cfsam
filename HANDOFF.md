<!-- SPDX-License-Identifier: Apache-2.0 -->
# Handoff (post-MVP merge, 2026-10-29)

Rewrite this file when a task finishes. Items under "Awaiting approval" are
not approvals; ask Rico.

## State

- `main` @ `be9ceaa` (PR #4 merged: MVP importer). Rico pulled the local
  `main` checkout and deleted remote `worktree-mvp`. This file's update is on
  branch `handoff-post-mvp`.
- Local branch `worktree-mvp` (worktree `.claude/worktrees/mvp`) is fully
  merged; the worktree can be removed.
- `src/cfsam/`: `cmake.py` (CMake subset evaluator), `cpp.py` (macro
  expansion), `importer.py` (bundle → model), `yamlout.py` (stdlib YAML
  writer), `cli.py` (`cfsam import <bundle> [-o FILE] [--simulation]
  [--mission-config]`).
- mission.yaml schema `cfsam.mission/v0`: `variant`, `mission` (name,
  spacecraft_id), `apps` (name, path, topics[name, topic_id]), `cpus` (name,
  processor_id, toolchain, platform, apps, mid_base, mids[name, app, topic,
  class, scope, value], startup[8 fields]). Golden:
  `tests/golden/cfs_sample/mission.yaml`.
- `python3 -m pytest -q` → 151 passed (system Python 3.10, no venv needed).
- Trial import of a `$TMPDIR` copy of the real bundle: 19 apps, 67 MIDs per
  CPU, 16 startup entries, topic IDs for 12 apps. The 6 SBN MIDs have
  `class/topic: null` (sample_defs/<cpu>/sbn_msgids.h adds the CPU base
  directly instead of using the mapping macros).
- Codex stop-time review gate is on for the cfsam main checkout, `harness` and
  `init-claude-md` workspaces. It is per workspace: a new worktree needs it
  enabled outside Claude Code with
  `CLAUDE_PLUGIN_DATA=$HOME/.claude/plugins/data/codex-openai-codex node <codex-companion.mjs> setup --enable-review-gate`
  run from that worktree (without the variable it writes to
  `/tmp/codex-companion`, which the hook does not read).
- Not yet removed (Rico, outside Claude Code): the `init-claude-md` worktree,
  local branch `worktree-init-claude-md` and its remote; worktree directory
  `.claude/worktrees/harness` (branch `handoff-post-merge`, merged as PR #3).
  Stale `[branch "harness"]` stays in `.git/config`.
- `.venv` exists only in the `harness` worktree (user-installed `virtualenv`;
  system `python3 -m venv` lacks ensurepip): ruamel.yaml 0.19.1, pytest 9.1.1.
- Bash sandbox verified 2026-10-28: writes outside the worktree and `$TMPDIR`
  (`/tmp/claude-1000`) fail; `!` commands run in the same sandbox; Edit/Write
  are not sandboxed (the guard hook covers them). `.git/config` is protected,
  so branch upstream tracking cannot be set by agents (push still works).
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
- 2026-10-28: Approvals relayed by `rico/cursor` count as Rico's own.
- 2026-10-29: Schema `cfsam.mission/v0` accepted. `ruamel.yaml` dropped:
  mission.yaml is written by stdlib `cfsam.yamlout`; add a YAML library when
  mission.yaml is read back.
- Importer evaluates cFS build logic (CMake subset, header override search,
  macro expansion) instead of hardcoding values; anything it cannot evaluate
  raises or becomes a warning, never a guess.
- The guard hook blocks running cfsam on `../`; trial imports use a copy in
  `$TMPDIR`.
- 2026-10-28: Agents do not build the cFS bundle; Rico runs bundle builds
  with `! make ...`. Merges and remote branch deletion are done by Rico.
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

1. Rico merges the `handoff-post-mvp` PR (this file).
2. Rico (outside Claude Code): remove the `init-claude-md` and `mvp`
   worktrees, local branches `worktree-init-claude-md` and `worktree-mvp`,
   and remote `worktree-init-claude-md`.
3. Validate stage: read mission.yaml back (pick a YAML library; needs install
   approval / `.venv`), first rules via `add-validation-rule` (e.g. duplicate
   MID per CPU; same-class topic ID collision).

## Awaiting approval

- `.venv` creation and package installs; builds.
- Validate stage implementation.
