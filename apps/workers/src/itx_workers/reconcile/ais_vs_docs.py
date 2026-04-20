def compare(ais_items: list[dict], doc_items: list[dict]) -> dict:
    return {
        "harmless": [],
        "duplicate": [],
        "missing_doc": [],
        "under_reporting": [],
        "prefill_issue": [],
        "human_decision": [],
        "counts": {
            "ais": len(ais_items),
            "docs": len(doc_items)
        }
    }
