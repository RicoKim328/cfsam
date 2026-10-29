# SPDX-License-Identifier: Apache-2.0
import pytest

from cfsam.yamlout import Hex, dump, scalar


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (None, "null"),
        (True, "true"),
        (7, "7"),
        (Hex(0x82, 2), "0x82"),
        (Hex(0x800, 4), "0x0800"),
        ("sample_app", "sample_app"),
        ("apps/sample_app", "apps/sample_app"),
        ("yes", '"yes"'),
        ("0x10", '"0x10"'),
        ("123", '"123"'),
        ("a b", '"a b"'),
        ("", '""'),
    ],
)
def test_scalar(value, text):
    assert scalar(value) == text


def test_dump_block_and_flow():
    text = dump(
        {
            "short": [1, 2],
            "empty": [],
            "items": [{"name": "a", "nested": [{"k": "v" * 120}]}],
        },
        header="line one\nline two",
    )
    assert text == (
        "# line one\n"
        "# line two\n"
        "short: [1, 2]\n"
        "empty: []\n"
        "items:\n"
        "  - name: a\n"
        "    nested:\n"
        f"      - k: {'v' * 120}\n"
    )


def test_dump_round_trips_through_a_yaml_parser():
    yaml = pytest.importorskip("yaml")
    data = {"a": [Hex(0x1882, 4), "x y", None], "b": {"c": "on", "d": [{"e": 1, "f": [1, 2]}]}}
    assert yaml.safe_load(dump(data)) == {"a": [0x1882, "x y", None], "b": {"c": "on", "d": [{"e": 1, "f": [1, 2]}]}}
