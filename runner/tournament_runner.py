from __future__ import annotations

import csv
import random
from collections import defaultdict
from pathlib import Path
from typing import Callable

from .match_runner import MatchResult, run_match


CSV_FIELDS = [
    "match_id",
    "p1_bot",
    "p2_bot",
    "winner",
    "reason",
    "total_turns",
    "p1_invalid_count",
    "p2_invalid_count",
    "p1_avg_time_ms",
    "p2_avg_time_ms",
    "seed",
    "log_file",
]


def run_tournament(
    p1_bot_path: str,
    p2_bot_path: str,
    games: int = 100,
    results_file: str | Path = "results/results.csv",
    seed: int | None = None,
    timeout_seconds: float = 5.0,
    on_match_complete: Callable[[int, int, MatchResult], None] | None = None,
) -> list[MatchResult]:
    base_rng = random.Random(seed)
    results_path = Path(results_file)
    results_path.parent.mkdir(parents=True, exist_ok=True)
    Path("logs/matches").mkdir(parents=True, exist_ok=True)

    results: list[MatchResult] = []
    for index in range(1, games + 1):
        match_id = f"match_{index:06d}"
        if index % 2 == 1:
            p1, p2 = p1_bot_path, p2_bot_path
        else:
            p1, p2 = p2_bot_path, p1_bot_path
        match_seed = base_rng.randrange(1_000_000_000)
        result = run_match(
            p1,
            p2,
            match_id=match_id,
            log_file=Path("logs/matches") / f"{match_id}.jsonl",
            seed=match_seed,
            timeout_seconds=timeout_seconds,
        )
        results.append(result)
        if on_match_complete:
            on_match_complete(index, games, result)

    with results_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_csv_row())
    return results


def format_match_progress(index: int, total_games: int, result: MatchResult) -> str:
    if result.winner == "DRAW":
        winner = "DRAW"
    else:
        winner_bot = result.p1_bot if result.winner == "P1" else result.p2_bot
        winner = f"{winner_bot} ({result.winner})"

    return (
        f"[{index:>3}/{total_games}] {result.match_id}: "
        f"{result.p1_bot}(P1) vs {result.p2_bot}(P2) -> "
        f"{winner} won, reason={result.reason}, turns={result.total_turns}, "
        f"invalid={result.p1_invalid_count}-{result.p2_invalid_count}"
    )


def summarize_tournament(results: list[MatchResult]) -> str:
    if not results:
        return "No games were played."

    bot_names = sorted({result.p1_bot for result in results} | {result.p2_bot for result in results})
    stats = {
        name: {
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "p1_wins": 0,
            "p2_wins": 0,
            "invalid": 0,
        }
        for name in bot_names
    }
    reason_counts: dict[str, int] = defaultdict(int)
    total_turns = 0
    draws = 0

    for result in results:
        total_turns += result.total_turns
        reason_counts[result.reason] += 1
        stats[result.p1_bot]["invalid"] += result.p1_invalid_count
        stats[result.p2_bot]["invalid"] += result.p2_invalid_count

        if result.winner == "DRAW":
            draws += 1
            stats[result.p1_bot]["draws"] += 1
            stats[result.p2_bot]["draws"] += 1
            continue

        winner_name = result.p1_bot if result.winner == "P1" else result.p2_bot
        loser_name = result.p2_bot if result.winner == "P1" else result.p1_bot
        stats[winner_name]["wins"] += 1
        stats[loser_name]["losses"] += 1
        if result.winner == "P1":
            stats[winner_name]["p1_wins"] += 1
        else:
            stats[winner_name]["p2_wins"] += 1

    lines = [
        "",
        "Tournament summary",
        "==================",
        f"Games: {len(results)}  Draws: {draws}  Avg turns: {total_turns / len(results):.1f}",
        "",
        f"{'Bot':<24} {'W':>4} {'L':>4} {'D':>4} {'Win%':>7} {'P1W':>5} {'P2W':>5} {'Invalid':>8}",
        "-" * 68,
    ]
    for name in sorted(bot_names, key=lambda bot: (-stats[bot]["wins"], stats[bot]["losses"], bot)):
        played = stats[name]["wins"] + stats[name]["losses"] + stats[name]["draws"]
        win_rate = (stats[name]["wins"] / played * 100.0) if played else 0.0
        lines.append(
            f"{name:<24} "
            f"{stats[name]['wins']:>4} "
            f"{stats[name]['losses']:>4} "
            f"{stats[name]['draws']:>4} "
            f"{win_rate:>6.1f}% "
            f"{stats[name]['p1_wins']:>5} "
            f"{stats[name]['p2_wins']:>5} "
            f"{stats[name]['invalid']:>8}"
        )

    lines.append("")
    lines.append("Reasons: " + ", ".join(f"{reason}={count}" for reason, count in sorted(reason_counts.items())))
    return "\n".join(lines)
