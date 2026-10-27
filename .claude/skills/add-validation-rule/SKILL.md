---
name: add-validation-rule
description: Step-by-step workflow for adding a mission.yaml validation rule to cfsam (fact-check, fixture, failing test, implementation, golden). Use whenever a new validate check is added or an existing one changes.
---
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Add a validation rule

Validation is read-only: a rule reports findings, it never rewrites
`mission.yaml` or the cFS tree.

1. **State the rule** in one sentence with its severity (error/warning) and the
   cFS behavior it protects, e.g. "error: two apps on one CPU use the same CMD
   MID".
2. **Fact-check** the cFS behavior with the `cfs-fact-checker` agent (see the
   `cfs-reference` skill). Record the `bundle/path:line` citations; drop or
   reword the rule if the agent cannot confirm it.
3. **Fixtures.** Use an existing `tests/fixtures/cfs_*` tree for the passing
   case. For the failing case, prefer a small `mission.yaml` written in the test
   over copying more cFS files. If a cFS file must change, copy it to a new
   fixture tree and mark it modified in its header and `SOURCE.md`.
4. **Write the tests first**: one passing case, one failing case per distinct
   finding, and a check that the finding message names the offending item.
   Run `python3 -m pytest -q` and see them fail.
5. **Implement** the rule next to the existing rules, following their pattern,
   with the citation in a comment. New files start with the SPDX header.
6. **Golden output.** If validate's report format is snapshotted, run
   `python3 -m pytest --update-golden`, then read the golden diff before
   accepting it.
7. **Run the full suite** and update `HANDOFF.md`.

Known trap: a command and a telemetry message may share a topic ID (sample_app
`SEND_HK` and `HK_TLM` are both 0x83). Uniqueness checks apply to MIDs, or to
topic IDs within the same CMD/TLM class.
