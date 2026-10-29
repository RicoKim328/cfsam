# SPDX-License-Identifier: Apache-2.0
"""A small evaluator for the subset of CMake used by cFS mission config files.

It understands ``set``, ``list(APPEND|REMOVE_ITEM)``, ``if/elseif/else/endif``
and skips ``function``/``macro`` bodies. Other commands are ignored. Anything
it cannot evaluate faithfully (an unknown ``if`` operator, unbalanced blocks)
raises ``CMakeError`` instead of guessing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


class CMakeError(Exception):
    pass


@dataclass(frozen=True)
class Arg:
    text: str
    quoted: bool


@dataclass(frozen=True)
class Command:
    name: str  # lower-cased
    args: tuple[Arg, ...]
    line: int


_FALSE_CONSTANTS = {"0", "OFF", "NO", "FALSE", "N", "IGNORE", "NOTFOUND", ""}
_TRUE_CONSTANTS = {"1", "ON", "YES", "TRUE", "Y"}


def parse(text: str) -> list[Command]:
    """Split CMake source into commands with their raw (unexpanded) arguments."""
    commands: list[Command] = []
    i, n, line = 0, len(text), 1
    name_re = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
        elif c.isspace():
            i += 1
        elif c == "#":
            while i < n and text[i] != "\n":
                i += 1
        else:
            m = name_re.match(text, i)
            if not m:
                raise CMakeError(f"line {line}: unexpected {c!r}")
            name, start_line = m.group().lower(), line
            i = m.end()
            while i < n and text[i] in " \t":
                i += 1
            if i >= n or text[i] != "(":
                raise CMakeError(f"line {line}: expected '(' after {name}")
            i += 1
            args: list[Arg] = []
            depth = 0
            while True:
                if i >= n:
                    raise CMakeError(f"line {start_line}: unterminated {name}(")
                c = text[i]
                if c == "\n":
                    line += 1
                    i += 1
                elif c.isspace():
                    i += 1
                elif c == "#":
                    while i < n and text[i] != "\n":
                        i += 1
                elif c == '"':
                    j = i + 1
                    buf = []
                    while j < n and text[j] != '"':
                        if text[j] == "\\" and j + 1 < n:
                            nxt = text[j + 1]
                            buf.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, "\\" + nxt))
                            j += 2
                            continue
                        if text[j] == "\n":
                            line += 1
                        buf.append(text[j])
                        j += 1
                    args.append(Arg("".join(buf), True))
                    i = j + 1
                elif c == "(":
                    depth += 1
                    args.append(Arg("(", False))
                    i += 1
                elif c == ")":
                    i += 1
                    if depth == 0:
                        break
                    depth -= 1
                    args.append(Arg(")", False))
                else:
                    j = i
                    while j < n and not text[j].isspace() and text[j] not in '()#"':
                        j += 1
                    args.append(Arg(text[i:j], False))
                    i = j
            commands.append(Command(name, tuple(args), start_line))
    return commands


class Evaluator:
    """Evaluates commands into ``self.vars`` (name -> CMake list string)."""

    def __init__(self, variables: dict[str, str] | None = None) -> None:
        self.vars: dict[str, str] = dict(variables or {})

    # -- public API ---------------------------------------------------------

    def run_file(self, path: Path) -> None:
        try:
            self.run(parse(path.read_text(encoding="utf-8")))
        except CMakeError as exc:
            raise CMakeError(f"{path}: {exc}") from None

    def run(self, commands: list[Command]) -> None:
        # Each frame: [parent_active, branch_taken, active]
        stack: list[list[bool]] = []
        active = True
        skip_depth = 0  # nesting inside function()/macro() bodies
        for cmd in commands:
            name = cmd.name
            if skip_depth:
                if name in ("function", "macro"):
                    skip_depth += 1
                elif name in ("endfunction", "endmacro"):
                    skip_depth -= 1
                continue
            if name == "if":
                taken = active and self._condition(cmd)
                stack.append([active, taken, taken])
                active = taken
            elif name == "elseif":
                frame = self._frame(stack, cmd)
                frame[2] = frame[0] and not frame[1] and self._condition(cmd)
                frame[1] = frame[1] or frame[2]
                active = frame[2]
            elif name == "else":
                frame = self._frame(stack, cmd)
                frame[2] = frame[0] and not frame[1]
                frame[1] = True
                active = frame[2]
            elif name == "endif":
                frame = self._frame(stack, cmd)
                stack.pop()
                active = frame[0]
            elif not active:
                continue
            elif name in ("function", "macro"):
                skip_depth = 1
            elif name == "set":
                self._set(cmd)
            elif name == "list":
                self._list(cmd)
        if stack or skip_depth:
            raise CMakeError("unterminated if() or function() block")

    def get_list(self, name: str) -> list[str]:
        return split_list(self.vars.get(name, ""))

    # -- commands -----------------------------------------------------------

    @staticmethod
    def _frame(stack: list[list[bool]], cmd: Command) -> list[bool]:
        if not stack:
            raise CMakeError(f"line {cmd.line}: {cmd.name}() without if()")
        return stack[-1]

    def _set(self, cmd: Command) -> None:
        args = self._expand_args(cmd.args)
        if not args:
            raise CMakeError(f"line {cmd.line}: set() without a variable")
        name, values = args[0], args[1:]
        for stop in ("CACHE", "PARENT_SCOPE"):
            if stop in values:
                values = values[: values.index(stop)]
        if values:
            self.vars[name] = ";".join(values)
        else:
            self.vars.pop(name, None)

    def _list(self, cmd: Command) -> None:
        args = self._expand_args(cmd.args)
        if len(args) < 2:
            raise CMakeError(f"line {cmd.line}: list() needs a sub-command and a variable")
        op, name, items = args[0].upper(), args[1], args[2:]
        current = self.get_list(name)
        if op == "APPEND":
            current += items
        elif op == "REMOVE_ITEM":
            current = [x for x in current if x not in items]
        else:
            raise CMakeError(f"line {cmd.line}: list({op}) is not supported")
        self.vars[name] = ";".join(current)

    # -- expansion ----------------------------------------------------------

    def expand(self, text: str) -> str:
        """Replace ``${VAR}`` (innermost first) and ``$ENV{VAR}`` (empty)."""
        pattern = re.compile(r"\$(ENV)?\{([^${}]*)\}")
        while True:
            new = pattern.sub(lambda m: "" if m.group(1) else self.vars.get(m.group(2), ""), text)
            if new == text:
                return new
            text = new

    def _expand_args(self, args: tuple[Arg, ...]) -> list[str]:
        out: list[str] = []
        for arg in args:
            value = self.expand(arg.text)
            if arg.quoted:
                out.append(value)
            else:
                out.extend(split_list(value))
        return out

    # -- if() conditions ----------------------------------------------------

    def _condition(self, cmd: Command) -> bool:
        tokens = [Arg(self.expand(a.text), a.quoted) for a in cmd.args]
        try:
            parser = _CondParser(tokens, self.vars)
            result = parser.parse_or()
            if parser.pos != len(tokens):
                raise CMakeError(f"unexpected {tokens[parser.pos].text!r}")
        except CMakeError as exc:
            raise CMakeError(f"line {cmd.line}: if(): {exc}") from None
        return result


class _CondParser:
    """Precedence: parentheses, unary (DEFINED), binary, NOT, AND, OR."""

    BINARY = {"STREQUAL", "EQUAL"}

    def __init__(self, tokens: list[Arg], variables: dict[str, str]) -> None:
        self.tokens = tokens
        self.vars = variables
        self.pos = 0

    def _peek(self) -> Arg | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _keyword(self, word: str) -> bool:
        tok = self._peek()
        if tok is not None and not tok.quoted and tok.text == word:
            self.pos += 1
            return True
        return False

    def parse_or(self) -> bool:
        result = self.parse_and()
        while self._keyword("OR"):
            rhs = self.parse_and()
            result = result or rhs
        return result

    def parse_and(self) -> bool:
        result = self.parse_not()
        while self._keyword("AND"):
            rhs = self.parse_not()
            result = result and rhs
        return result

    def parse_not(self) -> bool:
        if self._keyword("NOT"):
            return not self.parse_not()
        return self.parse_binary()

    def parse_binary(self) -> bool:
        if self._keyword("("):
            result = self.parse_or()
            if not self._keyword(")"):
                raise CMakeError("missing ')'")
            return result
        if self._keyword("DEFINED"):
            tok = self._take()
            return tok.text in self.vars
        lhs = self._take()
        op = self._peek()
        if op is not None and not op.quoted and op.text.isupper() and op.text not in ("AND", "OR", ")"):
            if op.text not in self.BINARY:
                raise CMakeError(f"operator {op.text} is not supported")
            self.pos += 1
            rhs = self._take()
            a, b = self._value(lhs), self._value(rhs)
            if op.text == "STREQUAL":
                return a == b
            try:
                return int(a) == int(b)
            except ValueError:
                return False
        return self._truthy(lhs)

    def _take(self) -> Arg:
        tok = self._peek()
        if tok is None:
            raise CMakeError("unexpected end of condition")
        self.pos += 1
        return tok

    def _value(self, tok: Arg) -> str:
        if not tok.quoted and tok.text in self.vars:
            return self.vars[tok.text]
        return tok.text

    def _truthy(self, tok: Arg) -> bool:
        if _is_constant(tok.text) or tok.quoted:
            return _constant_true(tok.text)
        value = self.vars.get(tok.text)
        return value is not None and not _constant_false(value)


def _is_constant(text: str) -> bool:
    up = text.upper()
    return up in _TRUE_CONSTANTS or up in _FALSE_CONSTANTS or up.endswith("-NOTFOUND") or _is_number(text)


def _is_number(text: str) -> bool:
    return re.fullmatch(r"-?\d+(\.\d+)?", text) is not None


def _constant_true(text: str) -> bool:
    up = text.upper()
    if up in _TRUE_CONSTANTS:
        return True
    if _is_number(text):
        return float(text) != 0
    return False


def _constant_false(text: str) -> bool:
    up = text.upper()
    return up in _FALSE_CONSTANTS or up.endswith("-NOTFOUND")


def split_list(value: str) -> list[str]:
    return [item for item in value.split(";") if item]
