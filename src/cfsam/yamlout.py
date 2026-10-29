# SPDX-License-Identifier: Apache-2.0
"""Deterministic YAML writer for mission.yaml (dicts, lists, scalars only).

Collections of scalars are written in flow style when they fit on one line,
otherwise in block style. Hex integers keep their hex spelling.
"""
from __future__ import annotations

import json
import re

FLOW_WIDTH = 100
_PLAIN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]*")
_RESERVED = {"null", "~", "true", "false", "yes", "no", "on", "off", "y", "n"}
_NUMBER_RE = re.compile(r"[-+]?(0x[0-9A-Fa-f_]+|0o?[0-7_]+|[\d_]+(\.[\d_]*)?([eE][-+]?\d+)?|\.\d+)")


class Hex(int):
    """An int written as ``0x...`` with at least ``digits`` hex digits."""

    digits: int

    def __new__(cls, value: int, digits: int = 1) -> "Hex":
        obj = super().__new__(cls, value)
        obj.digits = digits
        return obj

    def __repr__(self) -> str:
        return f"0x{int(self):0{self.digits}X}"


def scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Hex):
        return repr(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        if _PLAIN_RE.fullmatch(value) and value.lower() not in _RESERVED and not _NUMBER_RE.fullmatch(value):
            return value
        return json.dumps(value)
    raise TypeError(f"cannot write {type(value).__name__} to YAML")


def _is_scalar(value: object) -> bool:
    return not isinstance(value, (dict, list))


def _flow(value: object) -> str | None:
    """Flow-style text for a collection of scalars, or None."""
    if isinstance(value, list) and all(_is_scalar(v) for v in value):
        return "[" + ", ".join(scalar(v) for v in value) + "]"
    if isinstance(value, dict) and all(_is_scalar(v) for v in value.values()):
        return "{" + ", ".join(f"{scalar(k)}: {scalar(v)}" for k, v in value.items()) + "}"
    return None


def dump(data: dict, header: str = "") -> str:
    lines = [f"# {line}" if line else "#" for line in header.splitlines()]
    _mapping(data, 0, lines)
    return "\n".join(lines) + "\n"


def _mapping(data: dict, indent: int, lines: list[str], first_prefix: str | None = None) -> None:
    pad = " " * indent
    for idx, (key, value) in enumerate(data.items()):
        lead = first_prefix if (idx == 0 and first_prefix is not None) else pad
        head = f"{lead}{scalar(key)}:"
        _value(head, value, indent, lines)


def _value(head: str, value: object, indent: int, lines: list[str]) -> None:
    if _is_scalar(value):
        lines.append(f"{head} {scalar(value)}")
        return
    if not value:
        lines.append(f"{head} {'[]' if isinstance(value, list) else '{}'}")
        return
    flow = _flow(value)
    if flow is not None and len(head) + 1 + len(flow) <= FLOW_WIDTH:
        lines.append(f"{head} {flow}")
        return
    lines.append(head)
    if isinstance(value, dict):
        _mapping(value, indent + 2, lines)
    else:
        _sequence(value, indent + 2, lines)


def _sequence(items: list, indent: int, lines: list[str]) -> None:
    pad = " " * indent
    for item in items:
        if _is_scalar(item):
            lines.append(f"{pad}- {scalar(item)}")
            continue
        flow = _flow(item)
        if flow is not None and indent + 2 + len(flow) <= FLOW_WIDTH:
            lines.append(f"{pad}- {flow}")
        elif isinstance(item, dict) and item:
            _mapping(item, indent + 2, lines, first_prefix=f"{pad}- ")
        else:
            raise TypeError("nested empty or list-in-list items are not supported")
