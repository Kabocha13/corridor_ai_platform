from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


ActionKind = Literal["move", "wall"]
Orientation = Literal["h", "v"]


@dataclass(frozen=True)
class MoveAction:
    action: Literal["move"]
    to: str

    def to_json(self) -> dict[str, str]:
        return {"action": "move", "to": self.to}


@dataclass(frozen=True)
class WallAction:
    action: Literal["wall"]
    at: str
    orientation: Orientation

    def to_json(self) -> dict[str, str]:
        return {"action": "wall", "at": self.at, "orientation": self.orientation}


GameAction = MoveAction | WallAction


def action_from_json(data: dict[str, Any]) -> GameAction:
    if data.get("action") == "move" and isinstance(data.get("to"), str):
        return MoveAction(action="move", to=data["to"])
    if (
        data.get("action") == "wall"
        and isinstance(data.get("at"), str)
        and data.get("orientation") in ("h", "v")
    ):
        return WallAction(action="wall", at=data["at"], orientation=data["orientation"])
    raise ValueError(f"Invalid action JSON: {data!r}")


def action_key(action: GameAction | dict[str, Any]) -> tuple[Any, ...]:
    if isinstance(action, MoveAction):
        return ("move", action.to)
    if isinstance(action, WallAction):
        return ("wall", action.at, action.orientation)
    if isinstance(action, dict):
        if action.get("action") == "move":
            return ("move", action.get("to"))
        if action.get("action") == "wall":
            return ("wall", action.get("at"), action.get("orientation"))
    return ("invalid", repr(action))

