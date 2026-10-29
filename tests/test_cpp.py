# SPDX-License-Identifier: Apache-2.0
import pytest

from cfsam.cpp import CppError, MacroTable, evaluate_tokens, read_header, tokenize


def table_from(tmp_path, text: str) -> MacroTable:
    path = tmp_path / "h.h"
    path.write_text(text)
    table = MacroTable()
    table.add(read_header(path).macros)
    return table


def test_token_pasting_and_function_macros(tmp_path):
    table = table_from(
        tmp_path,
        """
        /* comment */
        #define BASE(x) BASE_##x
        #define BASE_CMD 0x1800
        #define TO_MIDV(topic) (BASE(CMD) | (topic))
        #define APP_TIDVAL(x) DEFAULT_APP_##x##_TOPICID
        #define APP_CMD_TOPICID APP_TIDVAL(CMD)
        #define DEFAULT_APP_CMD_TOPICID 0x82U // trailing comment
        #define APP_MIDVAL(x) TO_MIDV(APP_##x##_TOPICID)
        #define APP_CMD_MID APP_MIDVAL(CMD)
        """,
    )
    calls = []
    assert table.evaluate(["APP_CMD_MID"], lambda name, args: calls.append((name, args))) == 0x1882
    assert ("TO_MIDV", [["APP_CMD_TOPICID"]]) in calls


def test_line_continuation_and_first_definition_wins(tmp_path):
    table = table_from(tmp_path, "#define A (1 + \\\n 2)\n#define A 99\n")
    assert table.evaluate(["A"]) == 3


def test_unresolved_identifier_raises(tmp_path):
    table = table_from(tmp_path, "#define A (B + 1)\n")
    with pytest.raises(CppError, match="unresolved identifier B"):
        table.evaluate(["A"])


def test_self_reference_does_not_loop(tmp_path):
    table = table_from(tmp_path, "#define A A\n")
    with pytest.raises(CppError, match="unresolved identifier A"):
        table.evaluate(["A"])


def test_octal_and_shift():
    assert evaluate_tokens(tokenize("(010 << 4) | 0x1")) == 0x81


def test_includes_are_listed(tmp_path):
    path = tmp_path / "h.h"
    path.write_text('#include "a.h"\n#include <stdint.h>\n')
    assert read_header(path).includes == ["a.h"]
