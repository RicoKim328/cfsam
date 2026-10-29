# SPDX-License-Identifier: Apache-2.0
"""Import a cFS mission (apps, topic IDs, MIDs, startup script) into a model.

Read-only: nothing under the bundle is written. Citations are bundle-relative
paths at cFS ``dev`` @ ``d2f1477``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import cmake, cpp
from .yamlout import Hex

SCHEMA = "cfsam.mission/v0"

# cfe/modules/core_api/config/default_cfe_core_api_msgid_mapping.h:49,63,74,85
_MAPPING_RE = re.compile(r"CFE_(PLATFORM|GLOBAL)_(CMD|TLM)_TOPICID_TO_MIDV")


class MissionImportError(Exception):
    """A bundle the importer cannot interpret faithfully."""


@dataclass
class Bundle:
    root: Path
    mission_config: str = "sample"
    simulation: str = "native"
    warnings: list[str] = field(default_factory=list)

    @property
    def defs(self) -> Path:
        # MISSION_DEFS = ${MISSION_SOURCE_DIR}/${MISSIONCONFIG}_defs
        # (cfe/cmake/mission_build.cmake:80)
        return self.root / f"{self.mission_config}_defs"

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def import_mission(root: Path, mission_config: str = "sample", simulation: str = "native") -> tuple[dict, list[str]]:
    """Return ``(model, warnings)`` for the bundle at ``root``."""
    bundle = Bundle(root.resolve(), mission_config, simulation)
    if not (bundle.defs / "targets.cmake").is_file():
        raise MissionImportError(f"no {bundle.rel(bundle.defs)}/targets.cmake under {bundle.root}")

    # cfe/CMakeLists.txt:112-113: mission_defaults.cmake, then targets.cmake.
    # EDS stays off: CFE_EDS_ENABLED is left undefined.
    ev = cmake.Evaluator({"SIMULATION": simulation, "MISSIONCONFIG": mission_config})
    defaults = bundle.root / "cfe/cmake/mission_defaults.cmake"
    if defaults.is_file():
        ev.run_file(defaults)
    else:
        bundle.warn("cfe/cmake/mission_defaults.cmake not found; cFE default app list not applied")
    ev.run_file(bundle.defs / "targets.cmake")

    cpus = [_cpu_config(ev, name) for name in ev.get_list("MISSION_CPUNAMES")]
    if not cpus:
        raise MissionImportError("MISSION_CPUNAMES is empty")

    app_names: list[str] = []
    for cpu in cpus:
        for app in cpu["apps"]:
            if app not in app_names:
                app_names.append(app)

    search_path = ev.get_list("MISSION_MODULE_SEARCH_PATH")
    app_dirs = {name: _locate_module(bundle, ev, search_path, name) for name in app_names}
    apps = []
    topic_macros: dict[str, cpp.MacroTable] = {}
    for name in app_names:
        app_dir = app_dirs[name]
        if app_dir is None:
            bundle.warn(f"app {name}: source directory not found in module search path")
            apps.append({"name": name, "path": None, "topics": []})
            continue
        table, topics = _app_topics(bundle, name, app_dir)
        topic_macros[name] = table
        apps.append({"name": name, "path": bundle.rel(app_dir), "topics": topics})

    core_api = _locate_module(bundle, ev, search_path, "core_api")
    sb = _locate_module(bundle, ev, search_path, "sb")
    core_apps = _core_apps(bundle, ev, search_path)
    startup = _StartupScript(bundle)
    out_cpus = []
    for cpu in cpus:
        prefixes = [cpu["toolchain"], *cpu["platform"]]
        core = _core_macros(bundle, core_api, prefixes)
        mid_base = _mid_bases(bundle, core, cpu["name"])
        mids = []
        for name in cpu["apps"]:
            if app_dirs[name] is not None:
                mids += _app_mids(bundle, name, app_dirs[name], prefixes, core, topic_macros[name], cpu["name"])
        out_cpus.append(
            {
                "name": cpu["name"],
                "processor_id": cpu["processor_id"],
                "toolchain": cpu["toolchain"],
                "platform": cpu["platform"],
                "apps": cpu["apps"],
                "mid_base": mid_base,
                "sb_highest_valid_msgid": _sb_highest_valid_msgid(bundle, sb, prefixes, cpu["name"]),
                "mids": mids,
                "startup": [_with_entry_source(bundle, e, app_dirs) for e in startup.entries(cpu["apps"])],
            }
        )

    spacecraft = ev.vars.get("SPACECRAFT_ID")
    model = {
        "schema": SCHEMA,
        "variant": {"simulation": simulation, "eds": False},
        "mission": {
            "name": ev.vars.get("MISSION_NAME"),
            "spacecraft_id": _int_or_text(spacecraft) if spacecraft is not None else None,
        },
        "core_apps": core_apps,
        "apps": apps,
        "cpus": out_cpus,
    }
    return model, bundle.warnings


# -- targets.cmake ------------------------------------------------------------


def _cpu_config(ev: cmake.Evaluator, name: str) -> dict:
    # cfe/cmake/global_functions.cmake:350-358: SIMULATION overrides <cpu>_SYSTEM;
    # without either the toolchain is the CPU name.
    simulation = ev.vars.get("SIMULATION")
    toolchain = simulation or ev.vars.get(f"{name}_SYSTEM") or name
    # global_functions.cmake:362-363: <cpu>_PLATFORM defaults to "default <cpu>".
    platform = ev.get_list(f"{name}_PLATFORM") if f"{name}_PLATFORM" in ev.vars else ["default", name]
    # global_functions.cmake:376-378: MISSION_GLOBAL_APPLIST is appended to <cpu>_APPLIST.
    # Static apps (<cpu>_STATIC_APPLIST, :381-384) are not imported yet.
    apps = ev.get_list(f"{name}_APPLIST") + ev.get_list("MISSION_GLOBAL_APPLIST")
    proc = ev.vars.get(f"{name}_PROCESSORID")
    return {
        "name": name,
        "processor_id": _int_or_text(proc) if proc is not None else None,
        "toolchain": toolchain,
        "platform": platform,
        "apps": apps,
    }


def _locate_module(bundle: Bundle, ev: cmake.Evaluator, search_path: list[str], name: str) -> Path | None:
    # cfe/cmake/mission_build.cmake:399-405: first <searchdir>/<name> directory wins.
    # Not applied: $CFS_APP_PATH, which cFS puts in front of the path (:380-384).
    for entry in search_path + ev.get_list(f"{name}_SEARCH_PATH"):
        candidate = bundle.root / entry / name
        if candidate.is_dir():
            return candidate
    return None


# -- config header selection --------------------------------------------------


def _locate_config(bundle: Bundle, module_dir: Path | None, file_name: str, prefixes: list[str], mission_level: bool) -> Path | None:
    """Pick the header cFS would wrap as ``file_name``.

    Mirrors generate_configfile_set / generate_config_includefile /
    cfe_locate_implementation_file (cfe/cmake/global_functions.cmake:42-115,
    170-215, 237-282) for the non-EDS case.
    """
    target = file_name
    if mission_level:
        prefixes = []
        if file_name.startswith("cfe_"):
            # global_functions.cmake:201-204: mission-build cfe_* files match the
            # name without "cfe_", with MISSIONCONFIG and "cfe" as prefixes.
            target = file_name[len("cfe_"):]
            prefixes = [bundle.mission_config, "cfe"]

    defs = bundle.defs
    basedirs = [defs / p for p in prefixes if p != bundle.mission_config] + [defs]
    basedirs.reverse()
    basedirs += [d / "config" for d in basedirs]
    seen: list[Path] = []
    for d in basedirs:
        if d not in seen:
            seen.append(d)

    selected = None
    for d in seen:
        candidates = [d / target]
        reldir = "/" + d.relative_to(bundle.root).as_posix() + "/"
        candidates += [d / f"{p}_{target}" for p in prefixes if f"/{p}/" not in reldir]
        for c in candidates:
            if c.is_file():
                selected = c  # the last existing candidate has priority
    if selected is not None:
        return selected
    if module_dir is not None:
        fallback = module_dir / "config" / f"default_{file_name}"
        if fallback.is_file():
            return fallback
    return None


def _read_with_includes(bundle: Bundle, path: Path, table: cpp.MacroTable, seen: set[Path] | None = None) -> None:
    """Add ``path``'s macros, then those of quoted includes found next to it or in <defs>/inc."""
    seen = seen if seen is not None else set()
    if path in seen:
        return
    seen.add(path)
    header = cpp.read_header(path, bundle.rel(path))
    table.add(header.macros)
    for inc in header.includes:
        for d in (path.parent, bundle.defs / "inc"):
            if (d / inc).is_file():
                _read_with_includes(bundle, d / inc, table, seen)
                break


# -- topic IDs and MIDs -------------------------------------------------------


def _topic_re(app: str) -> re.Pattern[str]:
    # Both spellings occur: <APP>_MISSION_<X>_TOPICID (apps/sample_app/fsw/inc/
    # sample_app_topicids.h:28) and CFE_MISSION_<APP>_<X>_TOPICID (apps/cf/fsw/inc/
    # cf_topicids.h:34).
    up = re.escape(app.upper())
    return re.compile(rf"(?:{up}_MISSION|CFE_MISSION_{up})_(\w+)_TOPICID")


def _app_topics(bundle: Bundle, name: str, app_dir: Path) -> tuple[cpp.MacroTable, list[dict]]:
    table = cpp.MacroTable()
    topicids = app_dir / "fsw" / "inc" / f"{name}_topicids.h"
    if not topicids.is_file():
        return table, []
    header = cpp.read_header(topicids, bundle.rel(topicids))
    table.add(header.macros)
    values = _locate_config(bundle, app_dir, f"{name}_topicid_values.h", [], mission_level=True)
    if values is not None:
        _read_with_includes(bundle, values, table)

    pattern = _topic_re(name)
    topics = []
    for macro in header.macros:
        m = pattern.fullmatch(macro)
        if not m:
            continue
        try:
            value = table.evaluate([macro])
        except cpp.CppError as exc:
            bundle.warn(f"app {name}: topic {m.group(1)}: {exc}")
            continue
        topics.append({"name": m.group(1), "topic_id": Hex(value, 2)})
    return table, topics


def _core_macros(bundle: Bundle, core_api: Path | None, prefixes: list[str]) -> cpp.MacroTable:
    table = cpp.MacroTable()
    # cfe/modules/core_api/arch_build.cmake: per-CPU base values;
    # cfe/modules/core_api/mission_build.cmake: mission-wide mapping.
    for file_name, mission_level in (("cfe_core_api_base_msgid_values.h", False), ("cfe_core_api_msgid_mapping.h", True)):
        path = _locate_config(bundle, core_api, file_name, prefixes, mission_level)
        if path is None:
            bundle.warn(f"{file_name}: not found")
            continue
        _read_with_includes(bundle, path, table)
    return table


def _mid_bases(bundle: Bundle, core: cpp.MacroTable, cpu: str) -> dict:
    bases = {}
    for scope, macro in (("platform", "CFE_PLATFORM_BASE_MIDVAL"), ("global", "CFE_GLOBAL_BASE_MIDVAL")):
        for cls in ("CMD", "TLM"):
            key = f"{scope}_{cls.lower()}"
            try:
                bases[key] = Hex(core.evaluate([macro, "(", cls, ")"]), 4)
            except cpp.CppError as exc:
                bundle.warn(f"{cpu}: MID base {key}: {exc}")
                bases[key] = None
    return bases


def _sb_highest_valid_msgid(bundle: Bundle, sb: Path | None, prefixes: list[str], cpu: str) -> Hex | None:
    # cfe/modules/sb/fsw/inc/cfe_sb_internal_cfg.h:155-156 defines it through
    # CFE_PLATFORM_SB_CFGVAL from cfe_sb_internal_cfg_values.h, a per-CPU config
    # file (cfe/modules/sb/arch_build.cmake). A mission that replaces
    # cfe_sb_platform_cfg.h wholesale is not followed.
    macro = "CFE_PLATFORM_SB_HIGHEST_VALID_MSGID"
    table = cpp.MacroTable()
    internal = sb / "fsw" / "inc" / "cfe_sb_internal_cfg.h" if sb is not None else None
    if internal is None or not internal.is_file():
        bundle.warn(f"{cpu}: {macro}: cfe/modules/sb/fsw/inc/cfe_sb_internal_cfg.h not found")
        return None
    table.add(cpp.read_header(internal, bundle.rel(internal)).macros)
    values = _locate_config(bundle, sb, "cfe_sb_internal_cfg_values.h", prefixes, mission_level=False)
    if values is not None:
        _read_with_includes(bundle, values, table)
    try:
        return Hex(table.evaluate([macro]), 4)
    except cpp.CppError as exc:
        bundle.warn(f"{cpu}: {macro}: {exc}")
        return None


def _app_mids(
    bundle: Bundle,
    name: str,
    app_dir: Path,
    prefixes: list[str],
    core: cpp.MacroTable,
    topics: cpp.MacroTable,
    cpu: str,
) -> list[dict]:
    msgids = _locate_config(bundle, app_dir, f"{name}_msgids.h", prefixes, mission_level=False)
    if msgids is None:
        return []
    table = cpp.MacroTable()
    header = cpp.read_header(msgids, bundle.rel(msgids))
    _read_with_includes(bundle, msgids, table)
    values = _locate_config(bundle, app_dir, f"{name}_msgid_values.h", prefixes, mission_level=False)
    if values is not None:
        _read_with_includes(bundle, values, table)
    table.add(topics.macros)
    table.add(core.macros)

    topic_re = _topic_re(name)
    mids = []
    for macro in header.macros:
        if not macro.endswith("_MID") or header.macros[macro].params is not None:
            continue
        calls: list[tuple[str, list[list[str]]]] = []

        def on_call(callee: str, args: list[list[str]]) -> None:
            if _MAPPING_RE.fullmatch(callee):
                calls.append((callee, args))

        try:
            value = table.evaluate([macro], on_call)
        except cpp.CppError as exc:
            bundle.warn(f"{cpu}: app {name}: {macro}: {exc}")
            continue
        entry: dict = {"name": macro, "app": name, "topic": None, "class": None, "scope": None}
        if len(calls) == 1:
            callee, args = calls[0]
            m = _MAPPING_RE.fullmatch(callee)
            entry["scope"], entry["class"] = m.group(1).lower(), m.group(2).lower()
            arg = "".join(args[0]) if args else ""
            t = topic_re.fullmatch(arg)
            entry["topic"] = t.group(1) if t else arg
        entry["value"] = Hex(value, 4)
        mids.append(entry)
    return mids


# -- startup script -----------------------------------------------------------

_STARTUP_FIELDS = ("type", "file", "entry", "name", "priority", "stack", "load_addr", "exception_action")


class _StartupScript:
    """Evaluates <defs>/generate_startup.cmake for one CPU's app list.

    The script is installed with ``generate_cfs_startup_script(... ${<cpu>_APPLIST})``
    (sample_defs/cpu1/install_custom.cmake:48): fixed ``file(WRITE)`` lines, then one
    templated ``file(APPEND)`` line per ``CFS_APP_STARTUP_ORDER`` app found in the list.
    """

    def __init__(self, bundle: Bundle) -> None:
        self.bundle = bundle
        self.fixed: list[str] = []
        self.order: list[str] = []
        self.template: str | None = None
        path = bundle.defs / "generate_startup.cmake"
        if not path.is_file():
            bundle.warn(f"{bundle.rel(path)} not found; startup entries left empty")
            return
        for cmd in cmake.parse(path.read_text(encoding="utf-8")):
            args = cmd.args
            if cmd.name == "file" and args and args[0].text == "WRITE":
                self.fixed += [a.text for a in args[2:] if a.quoted]
            elif cmd.name == "file" and args and args[0].text == "APPEND":
                quoted = [a.text for a in args[2:] if a.quoted]
                if len(quoted) == 1:
                    self.template = quoted[0]
            elif cmd.name == "set" and args and args[0].text == "CFS_APP_STARTUP_ORDER":
                self.order = [a.text for a in args[1:]]
        if not self.fixed:
            bundle.warn(f"{bundle.rel(path)}: no fixed startup lines recognised")
        if self.order and self.template is None:
            raise MissionImportError(f"{bundle.rel(path)}: CFS_APP_STARTUP_ORDER without a recognised file(APPEND) template")

    def entries(self, applist: list[str]) -> list[dict]:
        lines = [line for chunk in self.fixed for line in chunk.splitlines()]
        for app in self.order:
            if app in applist and self.template is not None:
                lines += self.template.replace("${APP_UPPER}", app.upper()).replace("${APP}", app).splitlines()
        return [self._parse_line(line) for line in lines if line.strip()]

    def _parse_line(self, line: str) -> dict:
        fields = [f.strip() for f in line.strip().rstrip(";").split(",")]
        if len(fields) != len(_STARTUP_FIELDS):
            raise MissionImportError(f"startup line has {len(fields)} fields, expected 8: {line!r}")
        entry = dict(zip(_STARTUP_FIELDS, fields))
        for key in ("priority", "stack", "exception_action"):
            entry[key] = _int_or_text(entry[key])
        entry["load_addr"] = _int_or_text(entry["load_addr"])
        return entry


# -- core apps and entry symbols ----------------------------------------------


def _core_apps(bundle: Bundle, ev: cmake.Evaluator, search_path: list[str]) -> list[str] | None:
    """Names of the core apps ES registers before the startup script runs.

    cfe/cmake/target/CMakeLists.txt:55-71 puts the *_objtab.c entry of each of
    ``core_api ${MISSION_CORE_MODULES}`` in CFE_CORE_MODULE_OBJTAB; ES gives an
    AppTable record to the entries with a TaskMain
    (cfe/modules/es/fsw/src/cfe_es_start.c:802-873). Objtab files are looked up
    in <module>/fsw/src, where every cFE core module keeps it.
    """
    names = []
    for module in ["core_api", *ev.get_list("MISSION_CORE_MODULES")]:
        module_dir = _locate_module(bundle, ev, search_path, module)
        if module_dir is None:
            bundle.warn(f"core module {module} not found in module search path; core_apps left null")
            return None
        for path in sorted((module_dir / "fsw" / "src").glob("*_objtab.c")):
            text = path.read_text(encoding="utf-8", errors="replace")
            name = re.search(r'\.Name\s*=\s*"([^"]*)"', text)
            task = re.search(r"\.TaskMain\s*=\s*(\w+)", text)
            if name is None:
                bundle.warn(f"{bundle.rel(path)}: no .Name found; core_apps left null")
                return None
            if task is not None and task.group(1) != "NULL":
                names.append(name.group(1))
            break
    return names


def _with_entry_source(bundle: Bundle, entry: dict, app_dirs: dict[str, Path | None]) -> dict:
    # ES looks the entry up only in the module it just loaded
    # (OS_ModuleSymbolLookup, cfe/modules/es/fsw/src/cfe_es_apps.c:187-190), so
    # search that module's own sources. "NULL" or empty means no lookup (:187-188).
    # The file name maps to the module as in startup_unknown_module (validate.py).
    file = "".join(str(entry["file"]).split())
    symbol = "".join(str(entry["entry"]).split())
    module_dir = None if "/" in file else app_dirs.get(file.split(".", 1)[0])
    found = None
    if module_dir is not None and symbol not in ("", "NULL"):
        found = _find_definition(module_dir, symbol, bundle.root)
    return {**entry, "entry_source": found}


def _find_definition(module_dir: Path, symbol: str, root: Path) -> str | None:
    """``path:line`` of a non-static C function definition of ``symbol``.

    Only fsw/src and src are searched: unit-test stubs define the same names.
    A text search, not a compiler: a definition built by a macro is not found.
    """
    pattern = re.compile(
        rf"^(?!static\b)(?:[A-Za-z_][\w \t*]*[\s*])?{re.escape(symbol)}\s*\([^;{{}}]*\)\s*\{{",
        re.MULTILINE,
    )
    for sub in ("fsw/src", "src"):
        for path in sorted((module_dir / sub).glob("*.c")):
            text = path.read_text(encoding="utf-8", errors="replace")
            match = pattern.search(text)
            if match:
                line = text.count("\n", 0, match.start() + match.group(0).index(symbol)) + 1
                return f"{path.relative_to(root).as_posix()}:{line}"
    return None


def _int_or_text(text: str):
    text = text.strip()
    if re.fullmatch(r"0[xX][0-9A-Fa-f]+", text):
        return Hex(int(text, 16), max(1, len(text) - 2))
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text
