<!-- SPDX-License-Identifier: Apache-2.0 -->
# Handoff (post-merge, 2026-10-28)

Rewrite this file when a task finishes. Items under "Awaiting approval" are
not approvals; ask Rico.

## State

- Harness merged: PR #2 → `main` @ `3632918` (merge commit; Rico merged it
  outside Claude Code, since the auto-mode classifier denies agent merges).
  Branch `harness` was deleted (local and remote). Its stale
  `[branch "harness"]` section stays in `.git/config` (the sandbox protects
  that file).
- Not yet removed (sandbox / classifier blocked the agent; Rico does it
  outside Claude Code): the `init-claude-md` worktree, the local branch
  `worktree-init-claude-md` and its remote. All are merged into `main` and clean.
- Worktree `.claude/worktrees/harness` remains (directory name only); it is on
  branch `handoff-post-merge` (from `origin/main`), which holds this file's
  update and is not pushed.
- The local `main` checkout (`cfsam/`) is behind `origin/main`; Rico pulls it.
- Harness: `.claude/settings.json` (Bash sandbox + guard hook),
  `.claude/hooks/guard_cfs_readonly.py`, `.claude/skills/{cfs-reference,add-validation-rule}`,
  `.claude/agents/cfs-fact-checker.md`, `pyproject.toml`, `tests/conftest.py`,
  `tests/test_harness.py`, `tests/fixtures/cfs_sample/`, `.gitignore` additions.
- `.venv` (worktree root, gitignored) made with the user-installed
  `virtualenv` (system `python3 -m venv` lacks ensurepip/`python3.10-venv`):
  ruamel.yaml 0.19.1, pytest 9.1.1. `.venv/bin/python -m pytest -q` → 103 passed.
  A new worktree needs its own `.venv` (`python3 -m virtualenv .venv`).
- Bash sandbox is configured (`enabled`, `failIfUnavailable`,
  `allowUnsandboxedCommands: false`; bubblewrap + socat installed) and
  **verified** 2026-10-28 after a restart: writes to `~/Desktop` and to the
  cfsam main checkout fail with "Read-only file system"; writes in the
  worktree and `$TMPDIR` (`/tmp/claude-1000`) succeed. The bundle was not probed.
- The sandbox only covers Bash; Edit/Write are not sandboxed (the guard hook
  covers them).
- Sandbox placeholders: bubblewrap creates `/dev/null` char devices in the
  worktree for protected config paths (`.bashrc`, `.gitconfig`, `.mcp.json`,
  `.idea`, `.vscode`, `.claude/commands`, ...). They show as untracked; never
  commit them and do not gitignore them (Rico). Stage files by name, never
  `git add -A`.
- Guard hook (secondary layer) is allowlist-based after seven Codex
  stop-review rounds: a Bash segment touching the bundle must be read-only or
  a plain copy out of it; env/`~`/brace/glob expansion (not for names the
  command assigns), subshell-scoped cd, quoted $(...)/backtick bodies and
  for-loop variables are handled; non-read commands with targets it can't
  resolve are blocked. It also blocks bundle builds. It is a best-effort
  parser: code inside script files is not seen. `$TMPDIR` unset in the hook's
  env resolves to the sandbox's `/tmp/claude-<uid>`; a bare `TMPDIR` word in
  the command (possible reassignment) still leaves it unresolved.
- CLAUDE.md update applied 2026-10-28 (Rico confirmed in-session): Handoff
  line, Development workflow section, build line "run by Rico from the bundle
  root (`! make …`)", `@HANDOFF.md` at the end. The original draft text was
  lost; the applied text was rebuilt from the decisions below.
- Codex stop-time review gate was on for the `harness` and `init-claude-md`
  worktrees; check it for whichever worktree the MVP uses.

## Decisions

- 2026-10-28: Handoff via tracked `HANDOFF.md`, auto-loaded by `@HANDOFF.md`
  in CLAUDE.md; rewritten, not appended.
- 2026-10-28: Approvals relayed by `rico/cursor` count as Rico's own.
- 2026-10-28: Agents do not build the cFS bundle; Rico runs bundle builds
  himself with `! make ...` (the guard hook blocks them).
- 2026-10-28: Bundle write protection is Claude Code's Bash sandbox (OS
  level); the guard hook stays as a secondary layer. The bundle is not in
  `denyWrite` (that would make cfsam read-only too); the sandbox's default
  write scope is relied on.
- 2026-10-28: CLAUDE.md hook line says "Bundle builds are run by Rico
  (`! make …`)" and line 21 says build commands "are run by Rico from the
  bundle root (`! make …`)"; applied after Rico's in-session check.
- Fixtures are unmodified bundle copies at bundle-relative paths; tests never
  read the real bundle.
- No golden snapshots yet: mission.yaml schema is undecided.
- 2026-10-28: Guard hook treats `/tmp/claude-<uid>` as the safe `$TMPDIR`;
  sandbox placeholders are not gitignored; commits stage files by name.

## Next

1. Push `handoff-post-merge` and open its PR (this HANDOFF update).
2. Rico (outside Claude Code): `git worktree remove .claude/worktrees/init-claude-md`,
   `git branch -d worktree-init-claude-md`, `git push origin --delete worktree-init-claude-md`.
3. MVP: mission.yaml schema, importer for `cfs_sample`, first golden snapshot.

## Awaiting approval

- Pushing `handoff-post-merge`; its PR.
- MVP implementation; further package installs; builds.
- Merges and remote branch deletion: the auto-mode classifier denies them to
  agents; Rico runs them outside Claude Code. The sandbox also blocks deleting
  other worktrees' directories and writing `.git/config`.
