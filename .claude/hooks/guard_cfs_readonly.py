#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""PreToolUse hook: keep the surrounding cFS bundle read-only.

The bundle is the parent directory of the cfsam repository. Anything under it
except cfsam itself (including cfsam worktrees) is protected, and so are the
bundle's ancestor directories (deleting one deletes the bundle).

Edit/Write/NotebookEdit targets are checked exactly. Bash commands are checked
per segment (split at ; && || | & and newlines) with an allowlist. A segment
"touches" the bundle when it runs there after cd/pushd, names a protected path
anywhere in its words (after env, brace and glob expansion), or uses
git -C/--git-dir on it. Subshells and command/process substitutions are
separate segments (cd inside them does not leak out), and $(...)/`...` bodies
are also checked when quoted. for-loop variables are bound to their listed
values. A touching segment is allowed only if it is a known read-only command,
or a plain copy out of the bundle into cfsam. A non-read-only segment or
redirect whose target the hook cannot resolve (unset variable, $(...) output,
cd to an unknown directory, xargs input in a command that touches the bundle)
is blocked as well. Any redirect into the bundle is blocked.

This is a best-effort parser, not a sandbox: code inside script files and
exotic shell constructs are not inspected. Exit code 2 blocks the tool call and
shows stderr to Claude.
"""
from __future__ import annotations

import glob
import json
import os
import re
import shlex
import sys
from pathlib import Path

READ_ONLY = {
    "cat", "head", "tail", "grep", "egrep", "fgrep", "rg", "ls", "tree", "wc", "stat",
    "du", "diff", "cmp", "sort", "cut", "tr", "echo", "printf", "pwd", "realpath", "readlink",
    "basename", "dirname", "test", "[", "true", "false", "which", "md5sum", "sha1sum",
    "sha256sum", "column", "nl", "od", "hexdump", "strings", "jq", "read",
}
GIT_READ = {
    "log", "show", "diff", "status", "rev-parse", "ls-files", "ls-tree", "blame", "grep",
    "cat-file", "describe", "shortlog", "rev-list", "show-ref", "for-each-ref", "merge-base",
    "name-rev",
}
FIND_WRITE = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"}
XARGS_VALUE_OPTS = {"-n", "-I", "-L", "-P", "-d", "-E", "-s", "-a"}
PREFIXES = {"sudo", "env", "command", "nohup", "time", "exec", "do", "then", "else", "elif",
            "if", "while", "until", "!", "{", "(", "}", ")"}
# Subshells, command and process substitution are split out as their own segments.
SEPARATORS = {";", "&&", "||", "|", "&", "|&", ";;", "(", ")"}
PATHLIKE = re.compile(r"[\w.~$-]*/[\w./~$-]*|\.\.?")
# sed commands that write files or run shell: w/W (also the s///w flag) and e.
SED_WRITE = re.compile(r"(^|[\s;{}/\d$!])[wWe](\s|$)")


def cfsam_root(hook_file: Path) -> Path:
    """cfsam repo root, also when the hook runs from .claude/worktrees/<name>."""
    override = os.environ.get("CFSAM_ROOT")
    if override:
        return Path(override).resolve()
    repo = hook_file.resolve().parents[2]
    if repo.parent.name == "worktrees" and repo.parent.parent.name == ".claude":
        return repo.parents[2]
    return repo


# Variables the current command may (re)assign; their hook-time environment
# values are stale, so they are left unexpanded (= unresolved). Set per command.
VOLATILE: set[str] = set()


def bare_names(command: str) -> set[str]:
    """Names that appear outside a $name/${name} reference (x=, read x, export x, ...)."""
    return {
        m.group(1) for m in re.finditer(r"(?<![\w$])(?<!\$\{)([A-Za-z_]\w*)(?![\w(])", command)
    }


def expand(arg: str) -> str:
    def env(m: re.Match) -> str:
        name = m.group(1) or m.group(2)
        if name in VOLATILE:
            return m.group(0)
        return os.environ.get(name, m.group(0))

    # ~ is $HOME (also after = and : as in assignments), so it goes stale with HOME.
    arg = os.path.expanduser(re.sub(r"(^|[=:])~(?=/|$)", r"\1$HOME", arg))
    return re.sub(r"\$(?:(\w+)|\{(\w+)\})", env, arg)


def resolve(arg: str, cwd: Path) -> Path:
    return (cwd / expand(arg)).resolve()


def is_protected(path: Path, cfsam: Path) -> bool:
    bundle = cfsam.parent
    return path.is_relative_to(bundle) and not path.is_relative_to(cfsam)


def is_protected_or_ancestor(path: Path, cfsam: Path) -> bool:
    return is_protected(path, cfsam) or cfsam.parent.is_relative_to(path)


def braces(text: str, limit: int = 64) -> list[str]:
    """Expand one level of {a,b} at a time (enough for path arguments)."""
    m = re.search(r"\{([^{}]*,[^{}]*)\}", text)
    if not m or limit <= 0:
        return [text]
    out: list[str] = []
    for part in m.group(1).split(","):
        out += braces(text[: m.start()] + part + text[m.end():], limit - 1)
    return out


def candidates(value: str, cwd: Path) -> list[Path]:
    """Paths a shell word may refer to, after env, brace and glob expansion."""
    paths: list[Path] = []
    for item in braces(expand(value)):
        path = resolve(item, cwd)
        paths.append(path)
        if any(c in item for c in "*?["):
            paths += [Path(p).resolve() for p in glob.glob(str(cwd / item))[:256]]
    return paths


def lex(line: str) -> list[str]:
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = "#"
    try:
        return list(lexer)
    except ValueError:  # unbalanced quotes: fall back to a rough split
        return re.findall(r"[^\s;&|<>]+|[;&|<>]+", line)


def substitution_bodies(command: str) -> list[str]:
    """Bodies of $(...) and `...`, also inside double quotes (they still run)."""
    bodies: list[str] = []
    i = 0
    while (start := command.find("$(", i)) != -1:
        depth, j = 1, start + 2
        while j < len(command) and depth:
            depth += {"(": 1, ")": -1}.get(command[j], 0)
            j += 1
        bodies.append(command[start + 2:j - 1])
        i = start + 2
    bodies += command.split("`")[1::2]
    return bodies


def segments(command: str):
    """Yield word lists per simple command; subshell boundaries as ["("] / [")"]."""
    # Backticks become ( ... ); $(...), <(...), >(...) and (...) split at the parens.
    # Quoted parens stay inside their word.
    parts = command.split("`")
    command = "".join(p + (" ( " if k % 2 == 0 else " ) ") for k, p in enumerate(parts[:-1])) + parts[-1]
    command = command.replace("$(", " ( ").replace("(", " ( ").replace(")", " ) ")
    for line in command.splitlines():
        seg: list[str] = []
        for tok in lex(line):
            if tok in SEPARATORS:
                yield seg
                seg = []
                if tok in {"(", ")"}:
                    yield [tok]
            else:
                seg.append(tok)
        yield seg


VAR_REF = re.compile(r"\$\{?(\w+)\}?")


def bindable_loop_vars(command: str) -> set[str]:
    """for-loop variables that are never assigned elsewhere in the command.

    A name that appears bare anywhere besides its single for header (x=..., read x,
    declare x, a second loop, ...) may hold another value, so it stays unresolved.
    """
    names = re.findall(r"\b(?:for|select)\s+(\w+)\s+in\b", command)
    return {
        n for n in names
        if len(re.findall(r"(?<![\w$])(?<!\$\{)" + n + r"(?!\w)", command)) == 1
    }


def bind_loop_vars(seg: list[str], loopvars: dict[str, list[str]], limit: int = 64) -> list[list[str]]:
    """One copy of seg per combination of for-loop values it references."""
    names = sorted({n for tok in seg for n in VAR_REF.findall(tok) if loopvars.get(n)})
    variants = [seg]
    for name in names:
        pattern = re.compile(r"\$\{?" + name + r"\b\}?")
        variants = [[pattern.sub(lambda _: item, tok) for tok in v] for v in variants for item in loopvars[name]]
        variants = variants[:limit]
    return variants


def mentions_protected(words: list[str], cwd: Path, cfsam: Path) -> bool:
    for word in words:
        value = expand(word)
        if "=" in value and not value.startswith("/"):
            value = value.split("=", 1)[1]  # --opt=path, VAR=path
        for cand in {value, *PATHLIKE.findall(value)}:
            if cand and any(is_protected_or_ancestor(p, cfsam) for p in candidates(cand, cwd)):
                return True
    return False


def unresolved(words: list[str]) -> bool:
    """Words whose value the hook cannot know (unset/loop-less variables, $(...))."""
    return any("$" in expand(w) or "`" in w for w in words)


def git_subcommand(args: list[str]) -> tuple[list[str], str | None]:
    """Return (paths given to -C/--git-dir/--work-tree, subcommand)."""
    repos: list[str] = []
    j = 0
    while j < len(args) and args[j].startswith("-"):
        if args[j] in {"-C", "--git-dir", "--work-tree", "-c"} and j + 1 < len(args):
            if args[j] != "-c":
                repos.append(args[j + 1])
            j += 1
        elif "=" in args[j]:
            repos.append(args[j].split("=", 1)[1])
        j += 1
    return repos, (args[j] if j < len(args) else None)


def is_read_only(cmd: str, args: list[str]) -> bool:
    if any(a in {"-o", "--output"} or a.startswith(("--output=", "--pre")) for a in args):
        return False  # sort -o, git diff --output=, rg --pre, tree -o
    if cmd in {"sort", "tree"} and any(re.fullmatch(r"-[a-zA-Z]*o.*", a) for a in args):
        return False  # sort -uo FILE
    if cmd in READ_ONLY:
        return True
    if cmd == "sed":
        if any(a.startswith(("-i", "--in-place")) or re.fullmatch(r"-[a-zA-Z]*i\w*", a) for a in args):
            return False
        scripts: list[str] = []
        for i, a in enumerate(args):
            if a.startswith("--expression="):
                scripts.append(a.split("=", 1)[1])
            elif a == "--expression" or re.fullmatch(r"-[a-zA-Z]*e", a):
                scripts += args[i + 1:i + 2]
            elif re.fullmatch(r"-[a-zA-Z]*e.+", a):
                scripts.append(a[a.index("e") + 1:])
        if not scripts:
            scripts = [a for a in args if not a.startswith("-")][:1]
        return not any(SED_WRITE.search(s) for s in scripts) and "-f" not in args
    if cmd == "find":
        return not FIND_WRITE.intersection(args)
    if cmd == "git":
        # -c can set core.pager/diff.external and so run arbitrary commands.
        opts = args[: args.index(sub)] if (sub := git_subcommand(args)[1]) in args else args
        return sub in GIT_READ and not any(a.startswith(("-c", "--config-env")) for a in opts)
    if cmd == "xargs":
        j = 0
        while j < len(args) and args[j].startswith("-"):
            j += 2 if args[j] in XARGS_VALUE_OPTS else 1
        inner = args[j:]
        return bool(inner) and is_read_only(os.path.basename(inner[0]), inner[1:])
    return False


def is_plain_copy(cmd: str, args: list[str], cwd: Path, cfsam: Path) -> bool:
    """cp/rsync/install out of the bundle into a non-protected destination."""
    if cmd not in {"cp", "rsync", "install"} or is_protected(cwd, cfsam):
        return False
    for a in args:
        if a in {"--link", "--symbolic-link", "--remove-source-files", "--remove-destination"} \
                or a.startswith(("--link-dest", "--copy-dest", "--compare-dest")) \
                or (cmd == "cp" and re.fullmatch(r"-[a-zA-Z]*[ls][a-zA-Z]*", a)):
            return False  # hard/sym links and source removal can alter the bundle
    dest = None
    for i, a in enumerate(args):
        if a in {"-t", "--target-directory"} and i + 1 < len(args):
            dest = args[i + 1]
        elif a.startswith("--target-directory="):
            dest = a.split("=", 1)[1]
    if dest is None:
        paths = [a for a in args if not a.startswith("-")]
        dest = paths[-1] if len(paths) >= 2 else None
    return dest is not None and "$" not in expand(dest) and not any(
        is_protected_or_ancestor(p, cfsam) for p in candidates(dest, cwd)
    )


def bash_violations(command: str, cwd: Path, cfsam: Path, top: bool = True) -> list[str]:
    global VOLATILE
    if top:
        VOLATILE = bare_names(command)
    hits: list[str] = []
    # Commands run by $(...) / `...` are checked on their own, quoted or not.
    for body in substitution_bodies(command):
        hits += bash_violations(body, cwd, cfsam, top=False)

    parsed: list[tuple[str, list[str], list[str], Path, bool, bool]] = []
    command_touches = False
    any_unresolved = False
    unknown: list[str] = []  # redirects whose target can't be resolved statically
    dirstack: list[Path] = []
    subshells: list[tuple[Path, bool, list[Path]]] = []
    loopvars: dict[str, list[str]] = {}
    bindable = bindable_loop_vars(command)
    cwd_known = True
    for raw in segments(command):
        if raw == ["("]:  # cd inside a subshell or substitution does not leak out
            subshells.append((cwd, cwd_known, list(dirstack)))
            continue
        if raw == [")"]:
            if subshells:
                cwd, cwd_known, dirstack = subshells.pop()
            continue
        variants = bind_loop_vars(raw, loopvars)
        if len(variants) > 1 and any(t in {"cd", "pushd", "popd"} for t in raw):
            cwd_known = False  # cd to a loop-dependent directory
        for seg in variants:
            # Redirections: any target in the bundle is a write.
            words: list[str] = []
            i = 0
            while i < len(seg):
                tok = seg[i]
                if set(tok) <= set("<>&|") and ">" in tok and i + 1 < len(seg):
                    target = seg[i + 1]
                    if not (tok.endswith("&") and (target.isdigit() or target == "-")):
                        if "$" in expand(target) or not cwd_known:
                            unknown.append(f"redirect to {target}")
                        for path in candidates(target, cwd):
                            if is_protected(path, cfsam):
                                hits.append(f"redirect to {path}")
                    i += 2
                    continue
                if set(tok) <= set("<>&|"):
                    i += 2 if tok.startswith("<<") else 1
                    continue
                words.append(tok)
                i += 1
            touches = mentions_protected(words, cwd, cfsam)  # includes VAR=path assignments
            command_touches = command_touches or touches
            any_unresolved = any_unresolved or unresolved(words)
            while words and (words[0] in PREFIXES or re.fullmatch(r"\w+=.*", words[0])):
                words.pop(0)
            if not words:
                continue
            cmd, args = os.path.basename(words[0]), words[1:]
            if cmd in {"for", "select"}:
                # The loop header runs nothing; remember the values for $var.
                if len(args) >= 2 and args[1] == "in" and args[0] in bindable:
                    loopvars[args[0]] = [v for item in args[2:] for v in braces(expand(item))]
                continue
            if cmd in {"cd", "pushd", "popd"}:
                dest = next((a for a in args if not a.startswith(("-", "+"))), "~")
                if cmd == "pushd":
                    dirstack.append(cwd)
                if cmd == "popd":
                    if dirstack:
                        cwd = dirstack.pop()
                    else:
                        cwd_known = False  # stack from an earlier command
                elif "$" in expand(dest) or dest == "-" or any(c in dest for c in "*?["):
                    cwd_known = False
                else:
                    cwd = resolve(dest, cwd)
                continue
            touches = touches or is_protected(cwd, cfsam)
            if cmd == "git":
                touches = touches or any(is_protected(resolve(r, cwd), cfsam) for r in git_subcommand(args)[0])
            parsed.append((cmd, args, words, cwd, touches, cwd_known))

    command_touches = command_touches or bool(hits) or any(p[4] for p in parsed)
    hits += unknown
    for cmd, args, words, seg_cwd, touches, known in parsed:
        # A command with a target the hook can't see could be writing anywhere.
        opaque = unresolved(words) or not known
        if cmd in {"xargs", "parallel"}:
            opaque = opaque or command_touches or any_unresolved
        if not (touches or opaque) or is_read_only(cmd, args):
            continue
        if is_plain_copy(cmd, args, seg_cwd, cfsam):
            continue
        hits.append(f"{' '.join(words)} (cwd {seg_cwd if known else 'unknown'})")
    return hits


def main() -> int:
    event = json.load(sys.stdin)
    tool = event.get("tool_name", "")
    params = event.get("tool_input", {}) or {}
    cwd = Path(event.get("cwd") or os.getcwd())
    cfsam = cfsam_root(Path(__file__))

    if tool in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
        target = params.get("file_path") or params.get("notebook_path")
        hits = [str(resolve(target, cwd))] if target and is_protected(resolve(target, cwd), cfsam) else []
    elif tool == "Bash":
        hits = bash_violations(params.get("command", ""), cwd, cfsam)
    else:
        return 0

    if hits:
        print(
            f"Blocked: the cFS bundle at {cfsam.parent} is read-only reference material "
            f"(CLAUDE.md working rules). Only read-only commands may touch it. "
            f"Offending: {'; '.join(dict.fromkeys(hits))}. "
            "Copy files into cfsam (e.g. tests/fixtures/) instead; bundle builds are run by Rico (! make ...).",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
