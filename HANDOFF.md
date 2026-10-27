<!-- SPDX-License-Identifier: Apache-2.0 -->
# Handoff (harness, 2026-10-28)

Rewrite this file when a task finishes. Items under "Awaiting approval" are
not approvals; ask Rico.

## State

- Branch `harness` (worktree `.claude/worktrees/harness`), based on `main` @
  `d92e023` (PR #1 merge: CLAUDE.md, working rules, Apache-2.0). Harness
  committed and pushed to `origin/harness`; no PR yet.
- Harness: `.claude/settings.json` (Bash sandbox + guard hook),
  `.claude/hooks/guard_cfs_readonly.py`, `.claude/skills/{cfs-reference,add-validation-rule}`,
  `.claude/agents/cfs-fact-checker.md`, `pyproject.toml`, `tests/conftest.py`,
  `tests/test_harness.py`, `tests/fixtures/cfs_sample/`, `.gitignore` additions.
- `python3 -m pytest -q` → 100 passed (system Python 3.10, user-installed pytest;
  no venv, ruamel.yaml not installed).
- Bash sandbox is configured (`enabled`, `failIfUnavailable`,
  `allowUnsandboxedCommands: false`; bubblewrap + socat installed) but
  **not yet verified**: settings load at session start, and the session that
  added it still wrote outside the worktree. Verify after a restart.
- Guard hook (secondary layer) is allowlist-based after seven Codex
  stop-review rounds: a Bash segment touching the bundle must be read-only or
  a plain copy out of it; env/`~`/brace/glob expansion (not for names the
  command assigns), subshell-scoped cd, quoted $(...)/backtick bodies and
  for-loop variables are handled; non-read commands with targets it can't
  resolve are blocked. It also blocks bundle builds. It is a best-effort
  parser: code inside script files is not seen.
- CLAUDE.md diff is drafted (handoff lines, `@HANDOFF.md`, Development
  workflow incl. build line, line 21), not applied; Rico confirms it in-session.
- Codex stop-time review gate is on for the `harness` and `init-claude-md` worktrees.

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
  bundle root (`! make …`)"; approved, pending Rico's in-session check.
- Fixtures are unmodified bundle copies at bundle-relative paths; tests never
  read the real bundle.
- No golden snapshots yet: mission.yaml schema is undecided.

## Next

1. Restart the session in this worktree; run `/sandbox` and try a Bash write
   outside the worktree (e.g. `touch ~/Desktop/sandbox-probe`): it must fail.
   Never probe inside the bundle.
2. Rico reviews the CLAUDE.md diff and applies or approves it; commit it.
3. Open the harness PR.
4. Create `.venv`, install `ruamel.yaml` + pytest.
5. MVP: mission.yaml schema, importer for `cfs_sample`, first golden snapshot.

## Awaiting approval

- CLAUDE.md edit; PR.
- `.venv` creation and package installs; builds; MVP implementation.
- Removing the `init-claude-md` worktree or remote branch `worktree-init-claude-md`.
