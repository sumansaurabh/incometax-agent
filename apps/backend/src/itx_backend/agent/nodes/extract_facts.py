from __future__ import annotations

from itx_backend.agent.state import AgentState


def run(state: AgentState) -> AgentState:
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
            tax_facts[key] = value
            fact_evidence[key] = {
                "source_document": doc.get("id") or doc.get("name", "unknown"),
                "confidence": float(doc.get("confidence", 0.85)),
            }

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
