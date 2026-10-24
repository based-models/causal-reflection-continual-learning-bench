"""Runner output stays in the user message the coding encoder reads."""

from cr_clbench.constants import OBSERVATION_HEAD_CHARS
from cr_clbench.transcript import merge_user_turn, promote_runner_footer, runner_footer


def test_short_pytest_footer_stays_inline():
    text = "<returncode>0</returncode>\n<output>\n3 passed in 0.42s\n</output>"
    assert runner_footer(text) == "3 passed in 0.42s"
    assert promote_runner_footer(text) == text


def test_late_footer_is_copied_into_the_encoder_head():
    filler = "x" * (OBSERVATION_HEAD_CHARS + 50)
    text = f"<returncode>1</returncode>\n{filler}\n2 failed, 3 passed in 1.20s\n"
    promoted = promote_runner_footer(text)
    assert promoted.startswith("2 failed, 3 passed in 1.20s\n")
    assert text in promoted


def test_vitest_and_go_summaries_count():
    assert runner_footer("Tests  4 passed (4)\n") == "Tests  4 passed (4)"
    assert runner_footer("ok  example.com/pkg  0.12s\n") == "ok  example.com/pkg  0.12s"
    assert runner_footer("FAIL\tpkg/foo\n") == "FAIL\tpkg/foo"


def test_merge_keeps_one_turn_with_the_raw_output_and_the_prompt():
    observation = "<returncode>0</returncode>\n3 passed in 0.42s\n"
    merged = merge_user_turn(observation, "What's your next command?")
    assert merged.startswith("<returncode>0</returncode>")
    assert "3 passed in 0.42s" in merged
    assert merged.endswith("What's your next command?")
    assert "FEEDBACK:" not in merged
