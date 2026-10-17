"""Evidence manifests + tamper-evident ledger. LocalLedger is a working hash chain.
HederaLedger is a documented extension point and is NOT implemented."""
import hashlib, json, time


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def build_manifest(report, events_by_id):
    ids = sorted({i for s in report["narrative"]["sentences"] for i in s["event_ids"]})
    return {"moment_id": report["moment"]["id"], "language": report["language"], "audience": report["audience"],
            "source": report["narrative"]["source"], "sentences": report["narrative"]["sentences"],
            "events": [events_by_id[i].to_dict() for i in ids]}  # no personal data: synthetic IDs only


class LocalLedger:
    def __init__(self):
        self.entries = []

    def anchor(self, manifest_hash):
        prev = self.entries[-1]["entry_hash"] if self.entries else "0" * 64
        e = {"seq": len(self.entries), "manifest_hash": manifest_hash, "prev": prev, "ts": time.time()}
        e["entry_hash"] = sha256(e)
        self.entries.append(e)
        return e

    def verify(self, manifest, entry):
        """Proves the manifest is unchanged since anchoring, not that its claims are true."""
        body = {k: entry[k] for k in ("seq", "manifest_hash", "prev", "ts")}
        chain_ok = entry["entry_hash"] == sha256(body) and self.entries[entry["seq"]] == entry
        return {"manifest_unchanged": sha256(manifest) == entry["manifest_hash"], "ledger_entry_intact": chain_ok}


class HederaLedger:
    """TODO: submit manifest_hash to a Hedera Consensus Service topic and store the transaction id."""
    def anchor(self, manifest_hash):
        raise NotImplementedError("Hedera anchoring is not implemented in this starter")
