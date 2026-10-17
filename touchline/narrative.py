"""Fact-preserving multilingual narrative. Facts are built once; languages only re-render them.
Optional Foundry/LLM rendering is accepted ONLY if it passes validate_llm()."""
import json, os, re
from .events import TEAM_NAMES

T = {
 "en": {"turnover": "{m}' - {loser} lost possession{zone}.", "zone": " in the central zone",
        "counter": "{winner} countered and had a shot within {s} seconds.",
        "shot": "The move ended in a {res} (xG {xg}).", "goal": "goal", "miss": "shot",
        "control": "Control index before the turnover: {tci}/100 (heuristic, not a validated measure)."},
 "sw": {"turnover": "Dakika ya {m}: {loser} ilipoteza mpira{zone}.", "zone": " katikati ya uwanja",
        "counter": "{winner} ilishambulia haraka na kupiga shuti ndani ya sekunde {s}.",
        "shot": "Shambulio liliishia kwa {res} (xG {xg}).", "goal": "bao", "miss": "shuti",
        "control": "Kielezo cha udhibiti kabla ya kupoteza mpira: {tci}/100 (kadirio, si kipimo kilichothibitishwa)."},
 "fr": {"turnover": "{m}e minute : {loser} perd le ballon{zone}.", "zone": " dans l'axe central",
        "counter": "{winner} contre-attaque et tire en {s} secondes.",
        "shot": "L'action se termine par un {res} (xG {xg}).", "goal": "but", "miss": "tir",
        "control": "Indice de contrôle avant la perte de balle : {tci}/100 (heuristique, non validé)."},
 "es": {"turnover": "Minuto {m}: {loser} pierde el balón{zone}.", "zone": " en la zona central",
        "counter": "{winner} contraataca y dispara en {s} segundos.",
        "shot": "La jugada termina en {res} (xG {xg}).", "goal": "gol", "miss": "tiro",
        "control": "Índice de control antes de la pérdida: {tci}/100 (heurístico, no validado)."},
}
LANGS = tuple(T)


def build_facts(moment, events_by_id, control=None):
    shot = events_by_id[moment["shot_event_id"]]
    mid = [i for i in moment["event_ids"] if i not in (moment["turnover_event_id"], shot.id)]
    facts = [
        {"id": "f1", "kind": "turnover", "event_ids": moment["event_ids"][:2],
         "p": {"m": moment["minute"], "loser": TEAM_NAMES[moment["losing_team"]], "central": moment["central"]}},
        {"id": "f2", "kind": "counter", "event_ids": mid or [shot.id],
         "p": {"winner": TEAM_NAMES[moment["attacking_team"]], "s": moment["seconds_to_shot"]}},
        {"id": "f3", "kind": "shot", "event_ids": [shot.id], "p": {"xg": shot.xg, "goal": bool(shot.outcome)}}]
    if control is not None:
        facts.append({"id": "f4", "kind": "control", "event_ids": [], "p": {"tci": control}})
    return facts


def render(facts, lang="en"):
    t = T[lang]
    out = []
    for f in facts:
        p = dict(f["p"])
        if f["kind"] == "turnover":
            p["zone"] = t["zone"] if p.pop("central") else ""
        if f["kind"] == "shot":
            p["res"] = t["goal" if p.pop("goal") else "miss"]
        out.append({"text": t[f["kind"]].format(**p), "fact_ids": [f["id"]], "event_ids": f["event_ids"]})
    return out


NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _nums(v):
    return {s.replace(",", ".") for s in NUM.findall(str(v))}


def validate_llm(sentences, facts):
    """Reject LLM output that cites unknown facts or introduces numbers not in the facts."""
    by_id = {f["id"]: f for f in facts}
    allowed = set()
    for f in facts:
        for v in f["p"].values():
            allowed |= _nums(v)
        allowed |= {s for i in f["event_ids"] for s in _nums(i)}
    issues = []
    for s in sentences:
        ids = s.get("fact_ids") or []
        if not ids or any(i not in by_id for i in ids):
            issues.append(f"unknown or missing fact_ids: {ids}")
        for n in _nums(s.get("text", "")):
            if n not in allowed:
                issues.append(f"ungrounded number {n}")
    return issues


def llm_render(facts, lang, audience):
    """Optional Microsoft Foundry call (OpenAI-compatible endpoint). Returns None if not configured.
    NOT exercised by the offline test-suite."""
    ep, key, model = (os.getenv(k) for k in ("FOUNDRY_ENDPOINT", "FOUNDRY_API_KEY", "FOUNDRY_MODEL"))
    if not (ep and key and model):
        return None
    try:
        from openai import OpenAI
        r = OpenAI(base_url=ep, api_key=key).chat.completions.create(
            model=model, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": "You are a football commentator. Use ONLY the facts given. "
                       f"Write in language '{lang}' for a {audience} audience. Return JSON "
                       '{"sentences":[{"text":str,"fact_ids":[str]}]}. Do not add numbers or names not in the facts.'},
                      {"role": "user", "content": json.dumps(facts)}])
        sents = json.loads(r.choices[0].message.content)["sentences"]
    except Exception:
        return None
    if validate_llm(sents, facts):
        return None
    by_id = {f["id"]: f for f in facts}
    return [{**s, "event_ids": [e for i in s["fact_ids"] for e in by_id[i]["event_ids"]]} for s in sents]
