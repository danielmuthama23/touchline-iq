"""Event schema + consistency checks (stdlib only, so the core runs anywhere)."""
from dataclasses import dataclass, asdict
from typing import Optional

PITCH_X, PITCH_Y = 105.0, 68.0
EVENT_TYPES = {"pass", "interception", "carry", "shot", "tackle"}
TEAM_NAMES = {"home": "Harbour Rovers", "away": "Northgate United"}  # fictional


def other(team: str) -> str:
    return "away" if team == "home" else "home"


def in_final_third(x: float, team: str) -> bool:
    return x >= PITCH_X * 2 / 3 if team == "home" else x <= PITCH_X / 3


@dataclass(frozen=True)
class Event:
    id: str
    t: float            # match clock, seconds
    team: str           # "home" | "away"  (home attacks +x, away attacks -x)
    player: str         # H2..H11 / A2..A11
    type: str
    x: float
    y: float
    outcome: Optional[bool] = None   # pass completed / shot scored
    xg: Optional[float] = None

    def to_dict(self):
        return asdict(self)


def validate_events(events) -> list:
    """Return a list of human-readable problems (empty list = consistent)."""
    errors, seen, last = [], set(), -1.0
    for i, e in enumerate(events):
        if e.id in seen:
            errors.append(f"duplicate id {e.id}")
        seen.add(e.id)
        if e.t < last:
            errors.append(f"{e.id}: time goes backwards")
        last = e.t
        if e.type not in EVENT_TYPES:
            errors.append(f"{e.id}: unknown type {e.type}")
        if e.team not in ("home", "away"):
            errors.append(f"{e.id}: bad team")
        elif e.player[0] != ("H" if e.team == "home" else "A"):
            errors.append(f"{e.id}: player {e.player} not in team {e.team}")
        if not (0 <= e.x <= PITCH_X and 0 <= e.y <= PITCH_Y):
            errors.append(f"{e.id}: coordinates off pitch")
        if e.type == "shot" and e.xg is None:
            errors.append(f"{e.id}: shot without xg")
        if e.type == "pass" and e.outcome is False:  # possession logic
            nxt = events[i + 1] if i + 1 < len(events) else None
            if nxt is None or nxt.team == e.team or nxt.type not in ("interception", "tackle"):
                errors.append(f"{e.id}: failed pass not followed by opposing interception")
    return errors
