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


def _label(mid: dict) -> str:
    return f"{mid['name']} ({mid['app']})"


def mid_invalid(model: dict) -> Iterator[Finding]:
    """error: a MID is 0 or above the CPU's CFE_PLATFORM_SB_HIGHEST_VALID_MSGID."""
    # CFE_SB_IsValidMsgId: not CFE_SB_INVALID_MSG_ID (0) and <= HIGHEST_VALID_MSGID
    # (cfe/modules/sb/fsw/src/cfe_sb_msg_id_util.c:200-203; cfe_sb_api_typedefs.h:110).
    # SB rejects others at runtime: subscribe cfe_sb_api.c:981-984, transmit
    # cfe_sb_priv.c:889-891. Without the limit only 0 is checked.
    for cpu in model["cpus"]:
        highest = cpu.get("sb_highest_valid_msgid")
        for mid in cpu["mids"]:
            if mid["value"] == 0:
                yield Finding("error", "mid-invalid", cpu["name"], f"{_label(mid)} is 0x0000, the invalid MsgId")
            elif highest is not None and mid["value"] > highest:
                yield Finding(
                    "error",
                    "mid-invalid",
                    cpu["name"],
                    f"{_label(mid)} is {_hex(mid['value'])}, above CFE_PLATFORM_SB_HIGHEST_VALID_MSGID {_hex(highest)}",
                )


_CMD_BIT = 0x1000


def mid_class_bit(model: dict) -> Iterator[Finding]:
    """error: a cmd MID has the CCSDS packet-type bit clear, or a tlm MID has it set."""
    # MsgId v1 is the CCSDS StreamId (cfe/modules/msg/fsw/src/cfe_msg_msgid_v1.c:43,57-66);
    # bit 0x1000 is the packet type, 1 = CMD (cfe/modules/msg/fsw/inc/ccsds_hdr.h:53-58),
    # and cFS reads the type from it (cfe/modules/msg/fsw/src/cfe_msg_msgid_shared.c:32-51).
    for cpu in model["cpus"]:
        for mid in cpu["mids"]:
            if mid["class"] not in ("cmd", "tlm"):
                continue
            if (mid["class"] == "cmd") != bool(mid["value"] & _CMD_BIT):
                state = "clear" if mid["class"] == "cmd" else "set"
                yield Finding(
                    "error",
                    "mid-class-bit",
                    cpu["name"],
                    f"{_label(mid)} is class {mid['class']} but {_hex(mid['value'])} has the CMD bit 0x1000 {state}",
                )


def mid_cross_cpu(model: dict) -> Iterator[Finding]:
    """warning: platform MIDs of different CPUs have the same value."""
    # MID = base | topic (cfe/modules/core_api/config/default_cfe_core_api_msgid_mapping.h:49-86)
    # with per-CPU platform bases, so a wide topic can reach another CPU's base
    # (cpu1 0x1800 | 0x100 == cpu2 0x1900). This matters once CPUs share a bus (SBN).
    # Global MIDs are the same on every CPU by design and are skipped, as are
    # MIDs with an unknown scope.
    by_value: dict[int, dict[str, list[dict]]] = defaultdict(dict)
    for cpu in model["cpus"]:
        for mid in cpu["mids"]:
            if mid["scope"] == "platform":
                by_value[mid["value"]].setdefault(cpu["name"], []).append(mid)
    for value, cpus in by_value.items():
        if len(cpus) > 1:
            users = ", ".join(f"{_label(m)} on {name}" for name, mids in cpus.items() for m in mids)
            yield Finding("warning", "mid-cross-cpu", ", ".join(cpus), f"MID {_hex(value)} is used by {users}")


# Startup rules. ES logs a bad line and goes on with the next one, so the
# mission boots without that module: cfe/modules/es/fsw/src/cfe_es_startupscript.c:296-302
# ignores CFE_ES_ParseFileEntry's status.


def _token(value) -> str:
    """A startup field as ES reads it: only isgraph() chars are kept (cfe_es_startupscript.c:223)."""
    return "".join(str(value).split())


def _entry_label(entry: dict) -> str:
    return f"startup entry {_token(entry['name'])} ({_token(entry['file'])})"


def startup_unknown_module(model: dict) -> Iterator[Finding]:
    """error: a startup entry loads a module that is not built for its CPU."""
    # Only the CPU's <cpu>_APPLIST (with MISSION_GLOBAL_APPLIST) is installed to
    # exe/<cpu>/cf (cfe/cmake/global_functions.cmake:376-378, arch_build.cmake:540,790-792);
    # a missing file fails OS_ModuleLoad (cfe/modules/es/fsw/src/cfe_es_apps.c:167-176).
    # A file name with no '/' gets the /cf prefix and, without a '.', the module
    # extension (cfe/modules/fs/fsw/src/cfe_fs_api.c:470-540), so the module is the
    # part before the first '.'. Names with a '/' point elsewhere and are skipped.
    for cpu in model["cpus"]:
        apps = set(cpu["apps"])
        for entry in cpu["startup"]:
            file = _token(entry["file"])
            if "/" not in file and file.split(".", 1)[0] not in apps:
                yield Finding(
                    "error",
                    "startup-unknown-module",
                    cpu["name"],
                    f"{_entry_label(entry)} loads {file}, which is not in the CPU's apps",
                )


def startup_duplicate_name(model: dict) -> Iterator[Finding]:
    """error: two startup entries on one CPU have the same name."""
    # Apps and libraries share one name space: CFE_ES_AppCreate rejects an existing
    # app name, CFE_ES_LoadLibrary an existing lib or app name, with
    # CFE_ES_ERR_DUPLICATE_NAME (cfe/modules/es/fsw/src/cfe_es_apps.c:445-450,623-631);
    # an app named like a loaded lib fails OS_ModuleLoad with OS_ERR_NAME_TAKEN
    # (osal/src/os/shared/src/osapi-module.c:214). Names match case-sensitively
    # (cfe/modules/es/fsw/src/cfe_es_resource.c:97,132).
    for cpu in model["cpus"]:
        by_name: dict[str, list[dict]] = defaultdict(list)
        for entry in cpu["startup"]:
            by_name[_token(entry["name"])].append(entry)
        for name, entries in by_name.items():
            if len(entries) > 1:
                files = ", ".join(f"{_token(e['type'])} {_token(e['file'])}" for e in entries)
                yield Finding(
                    "error",
                    "startup-duplicate-name",
                    cpu["name"],
                    f"name {name} is used by {len(entries)} entries: {files}",
                )


def startup_bad_type(model: dict) -> Iterator[Finding]:
    """error: a startup entry's type is not CFE_APP or CFE_LIB."""
    # Exact strcmp, anything else is "Unexpected EntryType" and skipped
    # (cfe/modules/es/fsw/src/cfe_es_startupscript.c:362,406,415-419).
    for cpu in model["cpus"]:
        for entry in cpu["startup"]:
            if _token(entry["type"]) not in ("CFE_APP", "CFE_LIB"):
                yield Finding(
                    "error",
                    "startup-bad-type",
                    cpu["name"],
                    f"{_entry_label(entry)} has type {_token(entry['type'])}, expected CFE_APP or CFE_LIB",
                )


RULES: list[Callable[[dict], Iterator[Finding]]] = [
    mid_duplicate,
    mid_invalid,
    mid_class_bit,
    mid_cross_cpu,
    startup_unknown_module,
    startup_duplicate_name,
    startup_bad_type,
]


def validate(model: dict) -> list[Finding]:
    return [finding for rule in RULES for finding in rule(model)]
