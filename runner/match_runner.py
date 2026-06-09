from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.action import action_from_json, action_key
from engine.rules import apply_action, initial_state, legal_actions
from engine.serializer import action_to_json, state_for_ai, state_for_log
from engine.state import Player
from .bot_process import BotProcess


@dataclass
class MatchResult:
    match_id: str
    p1_bot: str
    p2_bot: str
    winner: str
    reason: str
    total_turns: int
    p1_invalid_count: int
    p2_invalid_count: int
    p1_avg_time_ms: float
    p2_avg_time_ms: float
    seed: int
    log_file: str

    def to_csv_row(self) -> dict[str, Any]:
        return {
            "match_id": self.match_id,
            "p1_bot": self.p1_bot,
            "p2_bot": self.p2_bot,
            "winner": self.winner,
            "reason": self.reason,
            "total_turns": self.total_turns,
            "p1_invalid_count": self.p1_invalid_count,
            "p2_invalid_count": self.p2_invalid_count,
            "p1_avg_time_ms": f"{self.p1_avg_time_ms:.3f}",
            "p2_avg_time_ms": f"{self.p2_avg_time_ms:.3f}",
            "seed": self.seed,
            "log_file": self.log_file,
        }


def run_match(
    p1_bot_path: str,
    p2_bot_path: str,
    match_id: str = "match_000001",
    log_file: str | Path | None = None,
    seed: int | None = None,
    timeout_seconds: float = 2.0,
) -> MatchResult:
    seed = random.randrange(1_000_000_000) if seed is None else seed
    rng = random.Random(seed)
    log_path = Path(log_file) if log_file else Path("logs/matches") / f"{match_id}.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    bots: dict[Player, BotProcess] = {
        "P1": BotProcess(p1_bot_path, timeout_seconds),
        "P2": BotProcess(p2_bot_path, timeout_seconds),
    }
    state = initial_state()
    invalid_counts: dict[Player, int] = {"P1": 0, "P2": 0}
    times: dict[Player, list[float]] = {"P1": [], "P2": []}

    try:
        with log_path.open("w", encoding="utf-8") as log:
            _write(log, {"type": "start", "match_id": match_id, "p1_bot": bots["P1"].name, "p2_bot": bots["P2"].name, "seed": seed})
            _write(log, state_for_log(state))

            while state.winner is None:
                player = state.turn
                legal = legal_actions(state)
                legal_by_key = {action_key(action): action for action in legal}
                reply = bots[player].request_action(state_for_ai(state, match_id, player))
                times[player].append(reply.thinking_time_ms)
                was_invalid = False
                invalid_detail: dict[str, Any] | None = None

                try:
                    if reply.error:
                        raise ValueError(reply.error)
                    if not reply.action or reply.action.get("type") != "action":
                        raise ValueError(f"missing type=action: {reply.action!r}")
                    candidate = action_from_json(reply.action)
                    if action_key(candidate) not in legal_by_key:
                        raise ValueError(f"not in legal_actions: {reply.action!r}")
                    selected = candidate
                except Exception as exc:
                    was_invalid = True
                    invalid_counts[player] += 1
                    selected = rng.choice(legal)
                    invalid_detail = {
                        "player": player,
                        "turn_index": state.turn_index + 1,
                        "raw_output": reply.raw_output,
                        "received": reply.action,
                        "error": str(exc),
                        "replacement_action": action_to_json(selected),
                    }

                action_log = {
                    "type": "action",
                    "turn_index": state.turn_index + 1,
                    "player": player,
                    "action": action_to_json(selected),
                    "thinking_time_ms": round(reply.thinking_time_ms, 3),
                    "was_invalid": was_invalid,
                }
                if invalid_detail:
                    action_log["invalid_detail"] = invalid_detail
                _write(log, action_log)
                state = apply_action(state, selected)
                _write(log, state_for_log(state))

            _write(
                log,
                {
                    "type": "end",
                    "winner": state.winner,
                    "reason": state.reason,
                    "total_turns": state.turn_index,
                    "p1_invalid_count": invalid_counts["P1"],
                    "p2_invalid_count": invalid_counts["P2"],
                },
            )
    finally:
        for bot in bots.values():
            bot.close()

    return MatchResult(
        match_id=match_id,
        p1_bot=bots["P1"].name,
        p2_bot=bots["P2"].name,
        winner=state.winner or "DRAW",
        reason=state.reason or "engine_error",
        total_turns=state.turn_index,
        p1_invalid_count=invalid_counts["P1"],
        p2_invalid_count=invalid_counts["P2"],
        p1_avg_time_ms=_avg(times["P1"]),
        p2_avg_time_ms=_avg(times["P2"]),
        seed=seed,
        log_file=str(log_path),
    )


def _write(handle, event: dict[str, Any]) -> None:
    handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
