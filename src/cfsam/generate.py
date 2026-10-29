# SPDX-License-Identifier: Apache-2.0
"""Generate cFS config files from a validated mission.yaml.

Output goes to a directory the caller names; the cFS tree is never written.
"""
from __future__ import annotations

from pathlib import Path

# Field order of a startup line, as in <defs>/generate_startup.cmake and
# CFE_ES_ParseFileEntry (cfe/modules/es/fsw/src/cfe_es_startupscript.c:342-390).
_FIELDS = ("type", "file", "entry", "name", "priority", "stack", "load_addr", "exception_action")


def _field(key: str, value) -> str:
    if key == "load_addr" and isinstance(value, int):
        return f"0x{value:X}"
    return str(value)


def startup_script(cpu: dict) -> str:
    """cfe_es_startup.scr text: one ``a, b, ...;`` line per entry.

    ES ends a line at ';' and splits fields at ',', dropping whitespace
    (cfe_es_startupscript.c:199-228), so this matches the cmake-written script
    field for field.
    """
    return "".join(", ".join(_field(k, e[k]) for k in _FIELDS) + ";\n" for e in cpu["startup"])


def write_startup_scripts(model: dict, out_dir: Path) -> list[Path]:
    paths = []
    for cpu in model["cpus"]:
        path = out_dir / cpu["name"] / "cfe_es_startup.scr"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(startup_script(cpu), encoding="utf-8")
        paths.append(path)
    return paths
