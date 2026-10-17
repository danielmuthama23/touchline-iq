"""Synthetic Match Foundry: seeded, scenario-constrained event generation."""
import math
import random
from .events import Event, PITCH_X, PITCH_Y, in_final_third, other

INJECT_T = 67 * 60 + 2  # scenario: central turnover at 67:02 -> counter -> shot at 67:11


def shot_xg(x, y, team):
    gx = PITCH_X if team == "home" else 0.0
    d = math.hypot(gx - x, PITCH_Y / 2 - y)
    return round(min(0.6, max(0.02, 1.2 * math.exp(-0.11 * d))), 2)  # toy model, not validated


def generate(seed: int = 42, minutes: int = 90):
    rng, ev, n = random.Random(seed), [], 0
    t, poss, x, y, injected = 0.0, "home", 52.5, 34.0, False

    def add(team, typ, ex, ey, outcome=None, xg=None, tt=None, player=None):
        nonlocal n
        n += 1
        p = player or f"{'H' if team == 'home' else 'A'}{rng.randint(2, 11)}"
        ev.append(Event(f"E{n:04d}", round(t if tt is None else tt, 1), team, p, typ,
                        round(min(PITCH_X, max(0, ex)), 1), round(min(PITCH_Y, max(0, ey)), 1), outcome, xg))

    while t < minutes * 60:
        if not injected and t >= INJECT_T - 12:
            for tt, team, pl, typ, ex, ey, oc in [
                (4022, "home", "H6", "pass", 52, 34, False),
                (4023, "away", "A8", "interception", 52, 34, None),
                (4024, "away", "A8", "carry", 46, 34, None),
                (4026, "away", "A8", "pass", 40, 34, True),
                (4028, "away", "A9", "carry", 26, 31, None)]:
                add(team, typ, ex, ey, oc, tt=tt, player=pl)
            add("away", "shot", 14, 32, True, shot_xg(14, 32, "away"), tt=4031, player="A9")
            t, poss, x, y, injected = 4045.0, "home", 52.5, 34.0, True
            continue
        t += rng.randint(4, 12)
        d = 1 if poss == "home" else -1
        if rng.random() < (0.86 if poss == "home" else 0.80):
            add(poss, "pass", x, y, True)
            x = min(PITCH_X, max(0, x + d * rng.uniform(-4, 10)))
            y = min(PITCH_Y, max(0, y + rng.uniform(-12, 12)))
            if in_final_third(x, poss) and rng.random() < 0.22:
                xg = shot_xg(x, y, poss)
                add(poss, "shot", x, y, rng.random() < xg, xg)
                poss = other(poss)
                x, y = (8.0, 34.0) if poss == "home" else (97.0, 34.0)
        else:
            add(poss, "pass", x, y, False)
            poss = other(poss)
            add(poss, "interception", x, y, tt=t + 1)
    return ev
