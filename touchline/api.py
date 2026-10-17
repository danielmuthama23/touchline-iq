"""FastAPI layer (thin). NOT run in the authoring sandbox: install requirements.txt and run the tests below."""
import os, tempfile
from pathlib import Path
from typing import Literal, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from .generator import generate
from .events import validate_events
from .analytics import find_dangerous_transitions, tci_series
from .agents import run_pipeline
from .provenance import LocalLedger, build_manifest, sha256
from .vision import detect_video, join_observations
from .microsoft import get_stack_state

app = FastAPI(title="TOUCHLINE IQ")
S = {"events": [], "by_id": {}, "reports": {}, "ledger": LocalLedger()}
MAX_VIDEO = 50 * 1024 * 1024


class ExplainReq(BaseModel):
    moment_id: Optional[str] = None
    audience: Literal["fan", "studio", "analyst"] = "fan"
    language: Literal["en", "sw", "fr", "es"] = "en"


def _load(seed):
    ev = generate(seed)
    if validate_events(ev):
        raise HTTPException(500, "generator produced inconsistent events")
    S.update(events=ev, by_id={e.id: e for e in ev}, reports={})


_load(42)


@app.get("/health")
def health():
    return {"ok": True, "foundry_configured": bool(os.getenv("FOUNDRY_ENDPOINT")), "events": len(S["events"])}


@app.get("/api/state")
def state():
    stack = get_stack_state()
    return {
        "ok": True,
        "events": len(S["events"]),
        "reports": len(S["reports"]),
        "foundry_configured": stack["capabilities"]["foundry"]["configured"],
        "capabilities": stack["capabilities"],
        "next_steps": stack["next_steps"],
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return (Path(__file__).parent.parent / "static" / "index.html").read_text()


@app.post("/api/match/generate")
def regenerate(seed: int = 42):
    _load(seed)
    return {"events": len(S["events"])}


@app.get("/api/match")
def match():
    return {"events": [e.to_dict() for e in S["events"]], "moments": find_dangerous_transitions(S["events"]),
            "tci": tci_series(S["events"])}


@app.post("/api/explain")
def explain(req: ExplainReq):
    try:
        r = run_pipeline(S["events"], req.moment_id, req.audience, req.language)
    except LookupError as e:
        raise HTTPException(404, str(e))
    if r["narrative"]:
        man = build_manifest(r, S["by_id"])
        entry = S["ledger"].anchor(sha256(man))
        rid = f"R{entry['seq']:04d}"
        S["reports"][rid] = {"manifest": man, "entry": entry}
        r["report_id"], r["manifest_hash"], r["ledger"] = rid, entry["manifest_hash"], "local-hash-chain"
    return r


@app.get("/api/verify/{report_id}")
def verify(report_id: str):
    rep = S["reports"].get(report_id)
    if not rep:
        raise HTTPException(404, "unknown report")
    return S["ledger"].verify(rep["manifest"], rep["entry"])


@app.post("/api/video")
async def video(offset: float = 0.0, file: UploadFile = File(...)):
    data = await file.read(MAX_VIDEO + 1)
    if len(data) > MAX_VIDEO:
        raise HTTPException(413, "video larger than 50 MB")
    with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
        f.write(data); f.flush()
        try:
            obs = detect_video(f.name)
        except RuntimeError as e:
            raise HTTPException(501, str(e))
    return {"observations": len(obs), "links": join_observations(obs, S["events"], offset)}
