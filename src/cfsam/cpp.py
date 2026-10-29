# SPDX-License-Identifier: Apache-2.0
"""Just enough of the C preprocessor to evaluate cFS topic ID and MID macros.

Supports object-like and function-like ``#define`` with ``##`` pasting and
``#include "..."`` discovery. Conditionals (``#if``/``#ifdef``) are not
evaluated: every ``#define`` in a file is collected, first definition wins.
"""
from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


class CppError(Exception):
    pass


@dataclass(frozen=True)
class Macro:
    name: str
    params: tuple[str, ...] | None  # None for object-like macros
    body: tuple[str, ...]
    source: str  # "path:line"


_TOKEN_RE = re.compile(
    r"\s*(?:(?P<id>[A-Za-z_]\w*)|(?P<num>(?:0[xX][0-9A-Fa-f]+|\d+)[uUlL]*)|(?P<op>##|<<|>>|[^\sA-Za-z0-9_]))"
)
_DEFINE_RE = re.compile(r"\s*#\s*define\s+([A-Za-z_]\w*)(\([^)]*\))?(.*)", re.S)
_INCLUDE_RE = re.compile(r'\s*#\s*include\s+"([^"]+)"')


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    pos = 0
    text = text.rstrip()
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            raise CppError(f"cannot tokenize {text[pos:]!r}")
        tokens.append(m.group(m.lastgroup))
        pos = m.end()
    return tokens


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """Strip comments and join backslash continuations; keep first line numbers."""
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group().count("\n"), text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    out: list[tuple[int, str]] = []
    buf, start = "", 0
    for lineno, raw in enumerate(text.split("\n"), 1):
        if not buf:
            start = lineno
        if raw.endswith("\\"):
            buf += raw[:-1] + " "
            continue
        out.append((start, buf + raw))
        buf = ""
    if buf:
        out.append((start, buf))
    return out


@dataclass
class Header:
    path: Path
    macros: dict[str, Macro]
    includes: list[str]


def read_header(path: Path, label: str | None = None) -> Header:
    label = label or str(path)
    macros: dict[str, Macro] = {}
    includes: list[str] = []
    for lineno, line in _logical_lines(path.read_text(encoding="utf-8")):
        m = _INCLUDE_RE.match(line)
        if m:
            includes.append(m.group(1))
            continue
        m = _DEFINE_RE.match(line)
        if not m:
            continue
        name, params, body = m.group(1), m.group(2), m.group(3)
        param_names = None
        if params is not None:
            param_names = tuple(p.strip() for p in params[1:-1].split(",") if p.strip())
        try:
            tokens = tuple(tokenize(body))
        except CppError as exc:
            raise CppError(f"{label}:{lineno}: {exc}") from None
        macros.setdefault(name, Macro(name, param_names, tokens, f"{label}:{lineno}"))
    return Header(path, macros, includes)


CallHook = Callable[[str, list[list[str]]], None]


class MacroTable:
    def __init__(self) -> None:
        self.macros: dict[str, Macro] = {}

    def add(self, macros: dict[str, Macro]) -> None:
        for name, macro in macros.items():
            self.macros.setdefault(name, macro)

    def expand(self, tokens: list[str], on_call: CallHook | None = None) -> list[str]:
        return self._expand(list(tokens), frozenset(), on_call)

    def evaluate(self, tokens: list[str], on_call: CallHook | None = None) -> int:
        expanded = self.expand(tokens, on_call)
        return evaluate_tokens(expanded)

    def _expand(self, tokens: list[str], active: frozenset[str], on_call: CallHook | None) -> list[str]:
        out: list[str] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            macro = self.macros.get(tok)
            if macro is None or tok in active:
                out.append(tok)
                i += 1
                continue
            if macro.params is None:
                out += self._expand(list(macro.body), active | {tok}, on_call)
                i += 1
                continue
            if i + 1 >= len(tokens) or tokens[i + 1] != "(":
                out.append(tok)
                i += 1
                continue
            args, i = _collect_args(tokens, i + 1, tok)
            if len(args) != len(macro.params) and not (len(macro.params) == 0 and args == [[]]):
                raise CppError(f"{tok} expects {len(macro.params)} argument(s), got {len(args)} ({macro.source})")
            if on_call is not None:
                on_call(tok, args)
            body = self._substitute(macro, args, active, on_call)
            out += self._expand(body, active | {tok}, on_call)
        return out

    def _substitute(self, macro: Macro, args: list[list[str]], active: frozenset[str], on_call: CallHook | None) -> list[str]:
        params = {p: a for p, a in zip(macro.params or (), args)}
        body = list(macro.body)
        result: list[str | None] = []  # None marks a pending paste
        for idx, tok in enumerate(body):
            if tok == "##":
                result.append(None)
                continue
            if tok in params:
                pasted = (idx > 0 and body[idx - 1] == "##") or (idx + 1 < len(body) and body[idx + 1] == "##")
                arg = params[tok]
                result.extend(arg if pasted else self._expand(list(arg), active, on_call))
            else:
                result.append(tok)
        out: list[str] = []
        paste_next = False
        for tok in result:
            if tok is None:
                paste_next = True
            elif paste_next and out:
                out[-1] = out[-1] + tok
                paste_next = False
            else:
                out.append(tok)
                paste_next = False
        return out


def _collect_args(tokens: list[str], open_idx: int, name: str) -> tuple[list[list[str]], int]:
    args: list[list[str]] = [[]]
    depth = 0
    i = open_idx + 1
    while i < len(tokens):
        tok = tokens[i]
        if tok == "(":
            depth += 1
        elif tok == ")":
            if depth == 0:
                return args, i + 1
            depth -= 1
        elif tok == "," and depth == 0:
            args.append([])
            i += 1
            continue
        args[-1].append(tok)
        i += 1
    raise CppError(f"unterminated argument list for {name}")


_BINOPS = {
    ast.BitOr: operator.or_,
    ast.BitAnd: operator.and_,
    ast.BitXor: operator.xor,
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
}
_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Invert: operator.invert}


def evaluate_tokens(tokens: list[str]) -> int:
    """Evaluate a fully expanded integer constant expression."""
    parts = []
    for tok in tokens:
        if re.fullmatch(r"[A-Za-z_]\w*", tok):
            raise CppError(f"unresolved identifier {tok} in {' '.join(tokens)}")
        m = re.fullmatch(r"(0[xX][0-9A-Fa-f]+|\d+)[uUlL]*", tok)
        if m:
            num = m.group(1)
            if len(num) > 1 and num[0] == "0" and num[1] not in "xX":
                num = "0o" + num[1:]  # C octal literal
            parts.append(num)
        else:
            parts.append(tok)
    expr = " ".join(parts)
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        raise CppError(f"not an integer expression: {expr}") from None
    return _eval_node(tree.body, expr)


def _eval_node(node: ast.AST, expr: str) -> int:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval_node(node.left, expr), _eval_node(node.right, expr))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval_node(node.operand, expr))
    raise CppError(f"unsupported construct in {expr}")
