# SPDX-License-Identifier: Apache-2.0
"""Validate a mission.yaml: read-only checks that report findings.

Each rule takes the loaded model and yields ``Finding``s; it never rewrites
mission.yaml or the cFS tree. Rules cite the cFS behavior they protect.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

import yaml

SCHEMA = "cfsam.mission/v0"


class MissionLoadError(Exception):
    pass


@dataclass(frozen=True)
class Finding:
    severity: str  # "error" or "warning"
    rule: str
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.severity}: [{self.rule}] {self.where}: {self.message}"


def load(path: Path) -> dict:
    try:
        model = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise MissionLoadError(f"{path}: {exc}") from exc
    if not isinstance(model, dict):
        raise MissionLoadError(f"{path}: top level is not a mapping")
    if model.get("schema") != SCHEMA:
        raise MissionLoadError(f"{path}: schema is {model.get('schema')!r}, expected {SCHEMA}")
    return model


def _hex(value: int) -> str:
    return f"0x{value:04X}"


def _message(mid: dict) -> tuple:
    """Identity of the message a MID names; aliases of one message share it."""
    if mid["topic"] is None:
        return ("name", mid["name"])
    return (mid["app"], mid["topic"], mid["class"], mid["scope"])


def mid_duplicate(model: dict) -> Iterator[Finding]:
    """error: two different messages on one CPU have the same MID value."""
    # SB keys routes by MsgId only and delivers to every subscriber, so two
    # messages on one MID get mixed with no runtime check:
    # cfe/modules/sb/fsw/src/cfe_sb_api.c:989-1058 (subscribe),
    # cfe/modules/sb/fsw/src/cfe_sb_priv.c:1052-1069 (transmit).
    # Compare computed values, not topic IDs: MID = base | topic
    # (cfe/modules/core_api/config/default_cfe_core_api_msgid_mapping.h:49-86),
    # and the OR lets e.g. cpu1 platform topic 0x60 equal global 0x1860.
    # Aliases are allowed: apps/sc/config/default_sc_msgids.h:50 defines
    # SC_1HZ_WAKEUP_MID as SC_WAKEUP_MID (same app, topic, class and scope).
    for cpu in model["cpus"]:
        by_value: dict[int, dict[tuple, list[dict]]] = defaultdict(dict)
        for mid in cpu["mids"]:
            by_value[mid["value"]].setdefault(_message(mid), []).append(mid)
        for value, messages in by_value.items():
            if len(messages) > 1:
                mids = [m for group in messages.values() for m in group]
                names = ", ".join(f"{m['name']} ({m['app']})" for m in mids)
                yield Finding("error", "mid-duplicate", cpu["name"], f"MID {_hex(value)} is used by {names}")


RULES: list[Callable[[dict], Iterator[Finding]]] = [mid_duplicate]


def validate(model: dict) -> list[Finding]:
    return [finding for rule in RULES for finding in rule(model)]
