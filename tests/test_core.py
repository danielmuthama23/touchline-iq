import unittest
from dataclasses import replace
from fastapi.testclient import TestClient
from touchline.generator import generate
from touchline.events import validate_events
from touchline.analytics import find_dangerous_transitions, tci
from touchline.agents import run_pipeline, evidence_agent
from touchline import narrative
from touchline.provenance import LocalLedger, build_manifest
from touchline.vision import Observation, join_observations
from touchline.api import app
from touchline.microsoft import get_stack_state

EV = generate(42)
BY = {e.id: e for e in EV}


class Core(unittest.TestCase):
    def test_reproducible_and_consistent(self):
        self.assertEqual(EV, generate(42))
        self.assertNotEqual(EV, generate(7))
        self.assertEqual(validate_events(EV), [])

    def test_validator_catches_problems(self):
        bad = EV[:3] + [EV[2]]
        self.assertTrue(any("duplicate" in e for e in validate_events(bad)))
        off = [replace(EV[0], x=500)]
        self.assertTrue(any("off pitch" in e for e in validate_events(off)))

    def test_scenario_moment_detected(self):
        m = next(x for x in find_dangerous_transitions(EV) if x["minute"] == 67)
        self.assertEqual((m["losing_team"], m["seconds_to_shot"], m["central"]), ("home", 9, True))
        self.assertTrue(all(i in BY for i in m["event_ids"]))

    def test_tci_range(self):
        for t in (600, 2400, 5400):
            self.assertTrue(0 <= tci(EV, t)["tci"] <= 100)

    def test_pipeline_all_languages(self):
        for lang in narrative.LANGS:
            for aud in ("fan", "studio", "analyst"):
                r = run_pipeline(EV, "M67-E0609" if "M67-E0609" in {m["id"] for m in find_dangerous_transitions(EV)} else None,
                                 aud, lang, use_llm=False)
                self.assertTrue(r["verification"]["verified"])
                self.assertEqual(r["narrative"]["source"], "template")
                self.assertTrue(all(i in BY for s in r["narrative"]["sentences"] for i in s["event_ids"]))
        self.assertEqual([a["agent"] for a in r["trace"]],
                         ["ingestion", "tactical", "evidence", "narrative", "personalization"])

    def test_same_facts_across_languages(self):
        m = find_dangerous_transitions(EV)[0]
        f = narrative.build_facts(m, BY)
        ids = [[s["event_ids"] for s in narrative.render(f, l)] for l in narrative.LANGS]
        self.assertTrue(all(x == ids[0] for x in ids))

    def test_evidence_agent_rejects_forged_claim(self):
        m = dict(find_dangerous_transitions(EV)[0])
        m["evidence"] = [{"claim": "x", "event_ids": ["E9999"]}]
        self.assertFalse(evidence_agent(m, BY)["verified"])

    def test_llm_output_validation(self):
        facts = narrative.build_facts(find_dangerous_transitions(EV)[0], BY)
        good = [{"text": "Rovers lost it.", "fact_ids": ["f1"]}]
        self.assertEqual(narrative.validate_llm(good, facts), [])
        self.assertTrue(narrative.validate_llm([{"text": "x", "fact_ids": ["f99"]}], facts))
        self.assertTrue(narrative.validate_llm([{"text": "He scored 17 goals.", "fact_ids": ["f1"]}], facts))

    def test_ledger_detects_tamper(self):
        r = run_pipeline(EV, audience="studio", use_llm=False)
        man, led = build_manifest(r, BY), LocalLedger()
        entry = led.anchor(__import__("touchline.provenance", fromlist=["sha256"]).sha256(man))
        self.assertTrue(all(led.verify(man, entry).values()))
        man["sentences"][0]["text"] += " (edited)"
        self.assertFalse(led.verify(man, entry)["manifest_unchanged"])

    def test_video_sync_offset(self):
        o = [Observation(10.0, [{"cls": "person", "conf": .9, "xyxy": [0, 0, 1, 1]}])]
        near = join_observations(o, EV, offset=4012.0)[0]   # match time 4022 -> turnover
        self.assertTrue(near["event_ids"])
        self.assertGreater(near["link_confidence"], 0.5)
        self.assertEqual(join_observations(o, EV, offset=100000.0)[0]["event_ids"], [])

    def test_state_endpoint_and_microsoft_capabilities(self):
        client = TestClient(app)
        resp = client.get("/api/state")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("capabilities", data)
        caps = {k for k, v in data["capabilities"].items() if isinstance(v, dict)}
        self.assertTrue({"foundry", "agent_framework", "fabric_eventstream", "cosmos_db", "azure_ai_search",
                         "azure_monitor", "hedera"}.issubset(caps))
        self.assertEqual(get_stack_state()["capabilities"]["foundry"]["status"], "not_configured")


if __name__ == "__main__":
    unittest.main()
