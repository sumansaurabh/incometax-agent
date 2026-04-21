from __future__ import annotations

from itx_backend.agent.state import AgentState


def _set_nested_evidence(evidence: dict, key_path: str, source_document: str, confidence: float) -> None:
    evidence[key_path] = {
        "source_document": source_document,
        "confidence": confidence,
    }


def _merge_tax_fact(
    target: dict,
    evidence: dict,
    key: str,
    value,
    source_document: str,
    confidence: float,
    parent_path: str = "",
) -> None:
    key_path = f"{parent_path}.{key}" if parent_path else key
    if isinstance(value, dict):
        existing = target.get(key)
        if not isinstance(existing, dict):
            existing = {}
        merged = dict(existing)
        for child_key, child_value in value.items():
            _merge_tax_fact(merged, evidence, child_key, child_value, source_document, confidence, key_path)
        target[key] = merged
        return

    target[key] = value
    _set_nested_evidence(evidence, key_path, source_document, confidence)


async def run(state: AgentState) -> AgentState:
    tax_facts = dict(state.get("tax_facts", {}))
    documents = state.get("documents", [])
    fact_evidence = dict(state.get("fact_evidence", {}))

    for doc in documents:
        fields = doc.get("normalized_fields", {})
        entities = doc.get("entities", [])

        # Prefer normalized structured fields when available.
        for key, value in fields.items():
            if value is None:
                continue
            _merge_tax_fact(
                tax_facts,
                fact_evidence,
                key,
                value,
                doc.get("id") or doc.get("name", "unknown"),
                float(doc.get("parser_confidence", doc.get("confidence", 0.85))),
            )

        # Fallback from entities for key identifiers.
        for entity in entities:
            entity_type = entity.get("type")
            entity_value = entity.get("value")
            confidence = float(entity.get("confidence", 0.75))
            if entity_type == "pan" and not tax_facts.get("pan"):
                tax_facts["pan"] = entity_value
                fact_evidence["pan"] = {
                    "source_document": doc.get("id") or doc.get("name", "unknown"),
                    "confidence": confidence,
                }
            if entity_type == "assessment_year" and not tax_facts.get("assessment_year"):
                tax_facts["assessment_year"] = entity_value
                fact_evidence["assessment_year"] = {
                    "source_document": doc.get("id") or doc.get("name", "unknown"),
                    "confidence": confidence,
                }

    messages = state.get("messages", [])
    messages.append(
        {
            "role": "assistant",
            "content": f"Extracted canonical facts: {len(tax_facts)} fields populated.",
            "metadata": {"node": "extract_facts"},
        }
    )

    state.apply_update({"messages": messages, "tax_facts": tax_facts, "fact_evidence": fact_evidence})
    return state
