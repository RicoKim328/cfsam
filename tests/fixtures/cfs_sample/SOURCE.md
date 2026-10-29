<!-- SPDX-License-Identifier: Apache-2.0 -->
# cfs_sample fixture

Unmodified copies of files from the NASA cFS bundle at commit `d2f1477`
(branch `dev`), kept at their bundle-relative paths. Original NASA headers and
the Apache-2.0 license apply; see `NOTICE`.

| File | What it gives the importer |
|---|---|
| `sample_defs/targets.cmake` | mission name, `MISSION_GLOBAL_APPLIST`, per-CPU app lists, native/EDS conditionals |
| `sample_defs/generate_startup.cmake` | how `cfe_es_startup.scr` is generated (fixed entries + `CFS_APP_STARTUP_ORDER`) |
| `sample_defs/inc/global_core_api_base_msgid_values.h` | per-CPU and global CMD/TLM MID bases |
| `apps/sample_app/fsw/inc/sample_app_topicids.h` | topic IDs (`CMD` 0x82, `SEND_HK` 0x83, `HK_TLM` 0x83) |
| `apps/sample_app/config/default_sample_app_*.h` | topic ID → MID mapping macros and MID names |
| `sample_defs/cpu1/cfe_core_api_base_msgid_values.h`, `sample_defs/cpu2/…` | per-CPU selection of the MID bases (`CFE_PLATFORM_BASE_MIDVAL`) |
| `cfe/modules/core_api/config/default_cfe_core_api_msgid_mapping.h` | topic ID → MID formula (`base \| topic`) |
| `cfe/modules/sb/fsw/inc/cfe_sb_internal_cfg.h` | `CFE_PLATFORM_SB_HIGHEST_VALID_MSGID` via `CFE_PLATFORM_SB_CFGVAL` (default 0x1FFF) |
| `cfe/modules/sb/config/default_cfe_sb_internal_cfg_values.h` | `CFE_PLATFORM_SB_CFGVAL(x)` → `DEFAULT_CFE_PLATFORM_SB_##x` (no override in `sample_defs`) |
| `cfe/cmake/mission_defaults.cmake` | defaults evaluated before `targets.cmake` (`cfe_assert cfe_testcase` in the global app list, module search path, `MISSION_CORE_MODULES`) |
| `cfe/modules/<m>/fsw/src/cfe_<m>_objtab.c` (config, es, evs, fs, sb, tbl, time, msg, sbr, resourceid) | core app names: entries with a `TaskMain` (ES, EVS, SB, TBL, TIME) |
| `osal/CMakeLists.txt`, `psp/CMakeLists.txt` | make the `osal` and `psp` core modules locatable (no objtab) |
| `apps/sample_app/fsw/src/sample_app.c` | definition of the startup entry `SAMPLE_APP_Main` (line 45) |

Only `sample_app` has source files here; the other listed apps are absent on
purpose, so the importer reports them as not found.

Note: `SEND_HK` (command) and `HK_TLM` (telemetry) share topic ID 0x83; that is
valid because CMD and TLM MIDs use different bases. Validation rules must not
flag it.

If a file is ever edited here, mark it as modified in its header.
