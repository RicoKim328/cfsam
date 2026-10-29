# SPDX-License-Identifier: Apache-2.0
import pytest

from cfsam.cmake import CMakeError, Evaluator, parse


def run(src: str, **variables: str) -> Evaluator:
    ev = Evaluator(variables)
    ev.run(parse(src))
    return ev


def test_set_list_and_nested_expansion():
    ev = run(
        """
        SET(MISSION_CPUNAMES cpu1)   # comment
        list(APPEND MISSION_CPUNAMES cpu2)
        set(cpu1_APPLIST ci_lab to_lab)
        set(NAME cpu1)
        set(OUT ${${NAME}_APPLIST} "a b")
        """
    )
    assert ev.get_list("MISSION_CPUNAMES") == ["cpu1", "cpu2"]
    assert ev.get_list("OUT") == ["ci_lab", "to_lab", "a b"]


def test_set_cache_and_unset():
    ev = run('set(A x CACHE STRING "doc")\nset(B y)\nset(B)')
    assert ev.vars["A"] == "x"
    assert "B" not in ev.vars


def test_list_remove_item():
    ev = run("set(L a b c)\nlist(REMOVE_ITEM L b)")
    assert ev.get_list("L") == ["a", "c"]


@pytest.mark.parametrize(
    ("condition", "variables", "expected"),
    [
        ('NOT CFE_EDS_ENABLED AND SIMULATION STREQUAL "native"', {"SIMULATION": "native"}, True),
        ('NOT CFE_EDS_ENABLED AND SIMULATION STREQUAL "native"', {"SIMULATION": "native", "CFE_EDS_ENABLED": "ON"}, False),
        ('NOT SIMULATION STREQUAL "i686-rtems5"', {"SIMULATION": "native"}, True),
        ('NOT SIMULATION STREQUAL "i686-rtems5"', {"SIMULATION": "i686-rtems5"}, False),
        ("CFE_EDS_ENABLED", {}, False),
        ("CFE_EDS_ENABLED", {"CFE_EDS_ENABLED": "OFF"}, False),
        ("NOT DEFINED X", {}, True),
        ("(A OR B) AND NOT C", {"B": "1"}, True),
    ],
)
def test_if_conditions(condition, variables, expected):
    ev = run(f"if ({condition})\n set(R yes)\nelse()\n set(R no)\nendif()", **variables)
    assert ev.vars["R"] == ("yes" if expected else "no")


def test_elseif_takes_first_true_branch_only():
    ev = run("if (A)\nset(R a)\nelseif (B)\nset(R b)\nelseif (C)\nset(R c)\nendif()", B="1", C="1")
    assert ev.vars["R"] == "b"


def test_inactive_branch_conditions_are_not_evaluated():
    # MATCHES is unsupported, but the branch is dead so it must not raise.
    run('if (FALSE)\n if (X MATCHES "y")\n endif()\nendif()')


def test_function_bodies_are_skipped():
    ev = run("function(f)\n set(X inside)\nendfunction()\nset(Y outside)")
    assert "X" not in ev.vars and ev.vars["Y"] == "outside"


def test_unsupported_operator_raises():
    with pytest.raises(CMakeError, match="MATCHES"):
        run('if (X MATCHES "y")\nendif()')


def test_unbalanced_if_raises():
    with pytest.raises(CMakeError):
        run("if (A)\nset(X 1)")
