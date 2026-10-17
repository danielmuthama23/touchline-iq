"""Four specialised agents with typed hand-offs over shared state.
Plain-Python orchestrator today; see README for the Microsoft Agent Framework port (not yet implemented)."""
import time
from .events import validate_events
from .analytics import find_dangerous_transitions, tci, HORIZON
from . import narrative


def _timed(trace, name, fn):
    t0 = time.perf_counter()
    out = fn()
    trace.append({"agent": name, "ms": round((time.perf_counter() - t0) * 1000, 2), "output": out})
    return out


def ingestion_agent(events):
    errs = validate_events(events)
    return {"ok": not errs, "events": len(events), "errors": errs[:5]}


def tactical_agent(events):
    return {"moments": find_dangerous_transitions(events)}


def evidence_agent(moment, by_id):
    """Independent re-check of every claim against the raw events."""
    issues = []
    for ev in moment["evidence"]:
        miss = [i for i in ev["event_ids"] if i not in by_id]
        if miss:
            issues.append(f"{ev['claim']}: unknown events {miss}")
    if not issues:
        turn, shot = by_id[moment["turnover_event_id"]], by_id[moment["shot_event_id"]]
        if not (turn.type == "pass" and turn.outcome is False and turn.team == moment["losing_team"]):
            issues.append("turnover is not a failed pass by the losing team")
        if not (shot.type == "shot" and shot.team == moment["attacking_team"]):
            issues.append("shot is not by the attacking team")
        if not 0 <= shot.t - turn.t <= HORIZON:
            issues.append("shot outside transition horizon")
    return {"verified": not issues, "issues": issues,
            "support_score": moment["support_score"] if not issues else 0.0}


def narrative_agent(moment, by_id, control, lang, audience, use_llm=True):
    facts = narrative.build_facts(moment, by_id, control if audience == "analyst" else None)
    sents = narrative.llm_render(facts, lang, audience) if use_llm else None
    return {"source": "foundry-llm" if sents else "template", "facts": facts,
            "sentences": sents or narrative.render(facts, lang)}


def personalization_agent(nar, moment, audience):
    s = nar["sentences"]
    if audience == "fan":
        return {"headline": s[0]["text"], "body": [x["text"] for x in s[1:3]]}
    if audience == "studio":
        return {"headline": f"{moment['minute']}' - key moment",
                "body": [f"[{moment['start_t']:.0f}s] {x['text']}" for x in s]}
    return {"headline": f"Analyst view, support score {moment['support_score']} (heuristic)",
            "body": [x["text"] for x in s]}


def run_pipeline(events, moment_id=None, audience="fan", language="en", use_llm=True):
    trace, by_id = [], {e.id: e for e in events}
    ing = _timed(trace, "ingestion", lambda: ingestion_agent(events))
    if not ing["ok"]:
        raise ValueError(f"inconsistent events: {ing['errors']}")
    moments = _timed(trace, "tactical", lambda: tactical_agent(events))["moments"]
    if not moments:
        raise LookupError("no dangerous transitions found")
    m = next((x for x in moments if x["id"] == moment_id), None) if moment_id else max(moments, key=lambda x: x["xg"])
    if m is None:
        raise LookupError(f"unknown moment {moment_id}")
    ev = _timed(trace, "evidence", lambda: evidence_agent(m, by_id))
    if not ev["verified"]:
        return {"moment": m, "verification": ev, "trace": trace, "narrative": None, "view": None}
    control = tci(events, m["start_t"])["tci"]
    nar = _timed(trace, "narrative", lambda: narrative_agent(m, by_id, control, language, audience, use_llm))
    view = _timed(trace, "personalization", lambda: personalization_agent(nar, m, audience))
    return {"moment": m, "verification": ev, "narrative": nar, "view": view, "trace": trace,
            "language": language, "audience": audience}
