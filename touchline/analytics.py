"""Deterministic analytics. The LLM never computes these numbers."""
from .events import in_final_third, other

W = {"P": 0.35, "S": 0.25, "T": 0.20, "R": 0.20}  # starting weights, NOT validated constants
HORIZON = 20.0


def tci(events, t_end, window=600, team="home"):
    """Touchline Control Index for `team` over the trailing window (0-100)."""
    ev = [e for e in events if t_end - window < e.t <= t_end]
    mine = [e for e in ev if e.team == team and e.type == "pass"]
    opp_half = (lambda e: e.x > 52.5) if team == "home" else (lambda e: e.x < 52.5)
    P = sum(e.outcome for e in mine) / len(mine) if mine else 0.5
    xm = sum(e.xg or 0 for e in ev if e.type == "shot" and e.team == team)
    xo = sum(e.xg or 0 for e in ev if e.type == "shot" and e.team != team)
    S = xm / (xm + xo) if xm + xo > 0 else 0.5
    T = sum(1 for e in mine if opp_half(e)) / len(mine) if mine else 0.5
    own = [e for e in mine if not opp_half(e)]
    R = 1 - sum(1 for e in own if not e.outcome) / len(own) if own else 0.5
    v = 100 * (W["P"] * P + W["S"] * S + W["T"] * T + W["R"] * R)
    return {"t": t_end, "tci": round(v, 1), "P": round(P, 2), "S": round(S, 2), "T": round(T, 2), "R": round(R, 2)}


def tci_series(events, step=300, window=600):
    end = events[-1].t if events else 0
    return [tci(events, t, window) for t in range(window, int(end) + 1, step)]


def find_dangerous_transitions(events, horizon=HORIZON):
    """Failed pass -> opponent possession -> shot within `horizon` seconds."""
    out = []
    for i, e in enumerate(events):
        if e.type != "pass" or e.outcome is not False:
            continue
        opp, chain = other(e.team), []
        for f in events[i + 1:]:
            if f.t - e.t > horizon or f.team == e.team:
                break
            chain.append(f)
            if f.type == "shot":
                break
        shot = chain[-1] if chain and chain[-1].type == "shot" else None
        if not shot:
            continue
        central = 35 <= e.x <= 70 and 22.7 <= e.y <= 45.3
        entry = next((f for f in chain if in_final_third(f.x, opp)), None)
        secs = round(shot.t - e.t)
        ev = [{"claim": "possession_lost_in_central_zone" if central else "possession_lost",
               "event_ids": [e.id, chain[0].id]}]
        if entry:
            ev.append({"claim": "opponent_reached_final_third", "event_ids": [entry.id]})
        ev.append({"claim": f"shot_within_{secs}s", "event_ids": [shot.id]})
        ids = [e.id] + [f.id for f in chain]
        out.append({
            "id": f"M{int(e.t // 60)}-{e.id}", "minute": int(e.t // 60), "start_t": e.t,
            "event_type": "dangerous_transition", "turnover_event_id": e.id, "shot_event_id": shot.id,
            "losing_team": e.team, "attacking_team": opp, "central": central, "seconds_to_shot": secs,
            "xg": shot.xg, "goal": bool(shot.outcome), "evidence": ev, "event_ids": ids,
            # heuristic score from event structure; not a calibrated probability
            "support_score": round(min(0.95, 0.55 + 0.4 * min(1, (shot.xg or 0) / 0.3)), 2),
            "claim_status": "supported_by_synthetic_events"})
    return out
