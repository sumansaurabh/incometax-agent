from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from asyncpg import Record

from itx_backend.db.session import get_pool
from itx_backend.services.documents import document_service


class ChatService:
    async def list_messages(self, thread_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select id, thread_id, role, content, message_type, metadata::text as metadata, created_at
                from chat_messages
                where thread_id = $1
                order by created_at desc
                limit $2
                """,
                thread_id,
                max(1, min(limit, 100)),
            )
        return [self._serialize(row) for row in reversed(rows)]

    async def handle_message(
        self,
        *,
        thread_id: str,
        message: str,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        user_message = await self._create_message(
            thread_id=thread_id,
            role="user",
            content=message,
            message_type="text",
            metadata={"context": context or {}},
        )
        agent_content, metadata = await self._build_agent_response(thread_id=thread_id, message=message)
        agent_message = await self._create_message(
            thread_id=thread_id,
            role="agent",
            content=agent_content,
            message_type="text",
            metadata=metadata,
        )
        return {
            "thread_id": thread_id,
            "user_message": user_message,
            "agent_message": agent_message,
        }

    async def _build_agent_response(self, *, thread_id: str, message: str) -> tuple[str, dict[str, Any]]:
        normalized = message.lower()
        documents = await document_service.list_documents(thread_id)
        parsed_count = sum(1 for document in documents if document.get("status") in {"parsed", "indexed"})
        indexed_count = sum(1 for document in documents if document.get("status") == "indexed")
        required_documents = ["Form 16", "AIS", "TIS", "bank interest certificates", "deduction proofs"]

        if "file" in normalized and ("return" in normalized or "itr" in normalized or "tax" in normalized):
            missing = self._missing_document_labels(documents)
            cards = [
                {
                    "id": "filing-readiness",
                    "kind": "document",
                    "title": "Filing readiness",
                    "body": "I will use uploaded documents first, search indexed chunks for missing facts, then ask only for gaps.",
                    "meta": [
                        {"label": "Uploaded", "value": str(len(documents))},
                        {"label": "Parsed", "value": str(parsed_count)},
                        {"label": "Indexed", "value": str(indexed_count)},
                    ],
                    "actions": [
                        {"id": "upload-documents", "label": "Upload documents"},
                        {"id": "search-documents", "label": "Search documents"},
                        {"id": "prepare-fill", "label": "Prepare portal fill"},
                    ],
                }
            ]
            if missing:
                return (
                    "I can start the return. Upload these if available: "
                    + ", ".join(missing)
                    + ". If they are already uploaded, I will search the indexed document content next.",
                    {"cards": cards, "missing_documents": missing},
                )
            return (
                "I can start the return with the uploaded documents. I will search the indexed evidence, extract facts, and prepare the filing flow.",
                {"cards": cards},
            )

        if "upload" in normalized or "document" in normalized:
            return (
                "Use the + button or drag PDFs, images, CSV, JSON, or text files into the chat. I will parse them and index searchable chunks.",
                {
                    "cards": [
                        {
                            "id": "upload-help",
                            "kind": "document",
                            "title": "Documents to upload",
                            "body": ", ".join(required_documents),
                            "actions": [{"id": "upload-documents", "label": "Upload documents"}],
                        }
                    ]
                },
            )

        if "refund" in normalized:
            return (
                "Open the refund-status page on the official portal and ask me to capture it, or share the refund status text here.",
                {"cards": [{"id": "refund-help", "kind": "summary", "title": "Refund status", "body": "I can capture the portal page when it is open."}]},
            )

        if "regime" in normalized:
            return (
                "I can compare old and new regimes once salary, deductions, and tax-paid facts are extracted from your documents.",
                {"cards": [{"id": "regime-help", "kind": "summary", "title": "Regime comparison", "actions": [{"id": "compare-regimes", "label": "Compare regimes"}]}]},
            )

        if documents:
            search = await document_service.semantic_search(thread_id=thread_id, query=message, top_k=3)
            results = search.get("results", [])
            if results:
                top = results[0]
                return (
                    f"I found a document-backed match in **{top['file_name']}**.",
                    {
                        "cards": [
                            {
                                "id": f"evidence-{top['document_id']}",
                                "kind": "evidence",
                                "title": str(top["file_name"]),
                                "body": str(top["chunk_text"])[:1000],
                                "meta": [
                                    {"label": "Score", "value": f"{float(top['score']):.3f}"},
                                    {"label": "Mode", "value": str(search.get("mode", "search"))},
                                ],
                            }
                        ]
                    },
                )

        return (
            "Tell me what you want to file or upload your tax documents. For example: **File my income tax return for the current year**.",
            {},
        )

    def _missing_document_labels(self, documents: list[dict[str, Any]]) -> list[str]:
        types = {str(document.get("document_type") or "").lower() for document in documents}
        missing: list[str] = []
        if not any("form16" in doc_type for doc_type in types):
            missing.append("Form 16")
        if not any("ais" in doc_type for doc_type in types):
            missing.append("AIS")
        if not any("tis" in doc_type for doc_type in types):
            missing.append("TIS")
        return missing

    async def _create_message(
        self,
        *,
        thread_id: str,
        role: str,
        content: str,
        message_type: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        pool = await get_pool()
        message_id = uuid.uuid4()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                insert into chat_messages (id, thread_id, role, content, message_type, metadata)
                values ($1, $2, $3, $4, $5, $6::jsonb)
                returning id, thread_id, role, content, message_type, metadata::text as metadata, created_at
                """,
                message_id,
                thread_id,
                role,
                content,
                message_type,
                json.dumps(metadata, sort_keys=True),
            )
        return self._serialize(row)

    def _serialize(self, row: Record) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "thread_id": row["thread_id"],
            "role": row["role"],
            "content": row["content"],
            "message_type": row["message_type"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            "created_at": row["created_at"].isoformat(),
        }


chat_service = ChatService()
