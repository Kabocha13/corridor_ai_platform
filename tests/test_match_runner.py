from pathlib import Path

from runner.match_runner import run_match


def test_invalid_action_is_replaced(tmp_path):
    bad_bot = tmp_path / "bad_bot.py"
    bad_bot.write_text('print("{not-json")\n', encoding="utf-8")
    result = run_match(
        str(bad_bot),
        "bots/shortest_path_bot.py",
        match_id="bad_match",
        log_file=tmp_path / "bad_match.jsonl",
        seed=1,
    )
    assert result.p1_invalid_count > 0
    assert result.winner in {"P1", "P2", "DRAW"}


def test_match_runs_to_completion(tmp_path):
    result = run_match(
        "bots/random_bot.py",
        "bots/shortest_path_bot.py",
        match_id="test_match",
        log_file=tmp_path / "test_match.jsonl",
        seed=2,
    )
    assert result.total_turns > 0
    assert Path(result.log_file).exists()
    assert result.winner in {"P1", "P2", "DRAW"}

