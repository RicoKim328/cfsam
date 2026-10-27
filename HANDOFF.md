<!-- SPDX-License-Identifier: Apache-2.0 -->
# Handoff (harness, 2026-10-28)

Rewrite this file when a task finishes. Items under "Awaiting approval" are
not approvals; ask Rico.

## State

- Branch `harness` (worktree `.claude/worktrees/harness`), based on `main` @
  `d92e023` (PR #1 merge: CLAUDE.md, working rules, Apache-2.0). Harness
  committed and pushed to `origin/harness`; PR #2 (`harness` → `main`,
  https://github.com/RicoKim328/cfsam/pull/2) is open, not merged.
- Harness: `.claude/settings.json` (Bash sandbox + guard hook),
  `.claude/hooks/guard_cfs_readonly.py`, `.claude/skills/{cfs-reference,add-validation-rule}`,
  `.claude/agents/cfs-fact-checker.md`, `pyproject.toml`, `tests/conftest.py`,
  `tests/test_harness.py`, `tests/fixtures/cfs_sample/`, `.gitignore` additions.
- `python3 -m pytest -q` → 103 passed (system Python 3.10, user-installed pytest;
  no venv, ruamel.yaml not installed).
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
  bundle root (`! make …`)"; applied after Rico's in-session check.
- Fixtures are unmodified bundle copies at bundle-relative paths; tests never
  read the real bundle.
- No golden snapshots yet: mission.yaml schema is undecided.
- 2026-10-28: Guard hook treats `/tmp/claude-<uid>` as the safe `$TMPDIR`;
  sandbox placeholders are not gitignored; commits stage files by name.

## Next

1. Rico reviews and merges PR #2.
2. Create `.venv`, install `ruamel.yaml` + pytest.
3. MVP: mission.yaml schema, importer for `cfs_sample`, first golden snapshot.

## Awaiting approval

- Merging PR #2.
- `.venv` creation and package installs; builds; MVP implementation.
- Removing the `init-claude-md` worktree or remote branch `worktree-init-claude-md`.
