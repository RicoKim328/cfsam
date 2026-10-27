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

Note: `SEND_HK` (command) and `HK_TLM` (telemetry) share topic ID 0x83; that is
valid because CMD and TLM MIDs use different bases. Validation rules must not
flag it.

If a file is ever edited here, mark it as modified in its header.
