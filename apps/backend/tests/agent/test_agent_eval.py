"""Phase 4 eval harness for the agentic upgrade.

These tests exercise the runner + registry end-to-end by mocking `llm_client.complete` to
return canned tool-use plans. The goal is to catch regressions where:
- A tool disappears from the registry
- A tool's input schema stops accepting the calls the model is trained to make
- The KB or how-to recipes stop returning expected entries for representative queries
- The runner loop's error handling changes in a user-visible way

No database, no network. Pure in-process functional tests — safe to run in CI on every PR.
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any, Optional
from unittest.mock import AsyncMock, patch

from itx_backend.agent import tools as _tools  # noqa: F401  (side effect registration)
from itx_backend.agent.runner import AgentRunner
from itx_backend.agent.tool_registry import tool_registry


def _tool_use_response(
    *,
    name: str,
    tool_input: dict,
    use_id: str = "call_1",
) -> dict[str, Any]:
    return {
        "stop_reason": "tool_use",
        "content": [
            {"type": "text", "text": f"calling {name}"},
            {"type": "tool_use", "id": use_id, "name": name, "input": tool_input},
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def _text_response(text: str) -> dict[str, Any]:
    return {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": 5, "output_tokens": 5},
    }


class RegistryContractTest(unittest.TestCase):
    """Regressions that would break production tool calling land here first."""

    EXPECTED_TOOLS = {
        "document_search",
        "extract_facts",
        "get_form_schema",
        "get_portal_context",
        "get_validation_errors",
        "how_to",
        "kb_lookup",
        "portal_nav",
        "propose_fill",
        "read_portal_field",
        "tax_calc",
        "web_search",
    }

    def test_all_expected_tools_registered(self) -> None:
        names = set(tool_registry.names())
        missing = self.EXPECTED_TOOLS - names
        extra = names - self.EXPECTED_TOOLS
        self.assertFalse(missing, f"missing tools: {missing}")
        # Extras are not failures but should be noted — they indicate new tools that should be
        # added to EXPECTED_TOOLS (and covered by tests below).
        if extra:
            self.skipTest(f"unregistered-but-present tools: {extra}")

    def test_every_tool_has_valid_anthropic_schema(self) -> None:
        for schema in tool_registry.anthropic_schemas():
            with self.subTest(tool=schema.get("name")):
                self.assertIn("name", schema)
                self.assertIn("description", schema)
                self.assertIn("input_schema", schema)
                self.assertEqual(schema["input_schema"].get("type"), "object")
                self.assertGreater(len(schema["description"]), 50,
                                   "descriptions must be long enough for the model to choose well")

    def test_tool_descriptions_mention_their_own_name_or_purpose(self) -> None:
        """Guards against the empty-description regression class."""
        for schema in tool_registry.anthropic_schemas():
            with self.subTest(tool=schema["name"]):
                desc = schema["description"].lower()
                self.assertTrue(
                    any(hint in desc for hint in ("use this", "call this", "return", "search", "lookup", "draft", "perform"))
                )


class KnowledgeBaseRegressionTest(unittest.TestCase):
    """A canned set of user queries that must land on the expected KB entry.

    Failures here almost always mean either the KB text or the scorer drifted.
    """

    def _search(self, query: str, topic: Optional[str] = None) -> list[str]:
        from itx_backend.agent.tools.kb_lookup import _kb

        return [match["id"] for match in _kb.search(query=query, topic=topic, top_k=3)]

    CASES = [
        # (query, expected_id_in_top_3, optional_topic)
        ("what is AIS", "ais", None),
        ("what is TIS", "tis", None),
        ("section 87A rebate", "rebate_87a", None),
        ("80C limit", "80c", None),
        ("80D health insurance", "80d", "sections"),
        ("234F late fee", "234f", None),
        ("ITR-1 eligibility", "itr1", "forms"),
        ("presumptive taxation 44AB", "presumptive_44ab", None),
        ("HRA exemption", "hra", None),
        ("standard deduction salary", "standard_deduction", None),
        ("updated return 139(8A)", "139_8a", None),
        ("belated return", "139_4", None),
        ("revised return", "139_5", None),
        ("surcharge rates", "surcharge", None),
        ("LTCG rate equity", "ltcg_rates", None),
    ]

    def test_canonical_queries_land_on_expected_entry(self) -> None:
        for query, expected_id, topic in self.CASES:
            with self.subTest(query=query):
                top = self._search(query, topic)
                self.assertIn(expected_id, top,
                              f"query '{query}' got {top}, expected {expected_id} in top-3")


class PortalHowToRegressionTest(unittest.TestCase):
    """Procedural how-to queries must land on the right recipe."""

    CASES = [
        ("how do I file my ITR", "file_itr"),
        ("check refund status", "check_refund_status"),
        ("how to e-verify", "e_verify_return"),
        ("download form 26as", "download_form_26as"),
        ("AIS download", "download_ais"),
        ("pre-validate bank", "update_bank_account"),
        ("revised return 139(5)", "revised_return"),
        ("belated return", "belated_return"),
        ("file itr-u", "updated_return"),
        ("pay self-assessment tax", "pay_tax_challan"),
        ("link aadhaar with pan", "link_aadhaar"),
        ("rectification 154", "rectification_154"),
        ("download ITR-V", "download_itrv"),
        ("raise grievance", "raise_grievance"),
    ]

    def test_how_to_search_lands_on_expected_recipe(self) -> None:
        from itx_backend.agent.tools.how_to import _index

        for query, expected in self.CASES:
            with self.subTest(query=query):
                results = _index.search(query, top_k=3)
                ids = [r.get("id") for r in results]
                self.assertIn(expected, ids, f"query '{query}' top-3 was {ids}")


class PortalNavTest(unittest.TestCase):
    def test_every_destination_returns_https_and_breadcrumb(self) -> None:
        from itx_backend.agent.tools.portal_nav import _DESTINATIONS

        for key, info in _DESTINATIONS.items():
            with self.subTest(destination=key):
                self.assertTrue(info["url"].startswith("https://"))
                self.assertIn("eportal.incometax.gov.in", info["url"])
                self.assertIn("breadcrumb", info)
                self.assertIn("label", info)


class WebSearchAllowlistTest(unittest.TestCase):
    def test_allowlist_contains_only_trusted_domains(self) -> None:
        from itx_backend.agent.tools.web_search import _ALLOWED_DOMAINS

        # Every allowlisted domain must be tax-relevant. No bare .com wildcards, no user
        # input leaks in. This test guards against accidental allowlist expansion.
        approved_suffixes = (
            "gov.in",
            "nic.in",
            "nsdl.com",
            "indiankanoon.org",
            "cleartax.in",
            "taxguru.in",
            "economictimes.indiatimes.com",
        )
        for domain in _ALLOWED_DOMAINS:
            with self.subTest(domain=domain):
                self.assertTrue(
                    any(domain.endswith(suffix) for suffix in approved_suffixes),
                    f"{domain} not in approved suffix list",
                )

    def test_unconfigured_returns_graceful_error(self) -> None:
        from itx_backend.agent.tools.web_search import web_search

        async def go() -> dict[str, Any]:
            return await web_search(thread_id="t1", query="any")

        result = asyncio.run(go())
        self.assertEqual(result.get("results"), [])
        # Either an error or a hint field — never a crash.
        self.assertTrue(result.get("error") or result.get("hint"))


class HybridRetrieverMathTest(unittest.TestCase):
    """RRF and merge behaviour — pure functions, no DB."""

    def test_rrf_monotonicity(self) -> None:
        from itx_backend.services.hybrid_retriever import _rrf

        self.assertEqual(_rrf(None, 60), 0.0)
        self.assertGreater(_rrf(1, 60), _rrf(2, 60))
        self.assertGreater(_rrf(10, 60), 0.0)

    def test_merge_collapses_same_chunk_across_sources(self) -> None:
        from itx_backend.services.hybrid_retriever import Candidate, HybridRetriever

        retriever = HybridRetriever()
        dense = [Candidate(
            chunk_id="qdrant:1", document_id="A", chunk_text="abc", file_name="f.pdf",
            document_type="form16", page_number=1, section_name=None,
            dense_score=0.9, dense_rank=1, source_tags=["dense"],
        )]
        bm25 = [Candidate(
            chunk_id="pg_uuid", document_id="A", chunk_text="abc", file_name="f.pdf",
            document_type="form16", page_number=1, section_name=None,
            bm25_score=2.0, bm25_rank=1, source_tags=["bm25"],
        )]
        merged = retriever._merge(dense_hits=dense, bm25_hits=bm25)
        self.assertEqual(len(merged), 1)
        only = next(iter(merged.values()))
        self.assertEqual(only.dense_rank, 1)
        self.assertEqual(only.bm25_rank, 1)
        self.assertIn("dense", only.source_tags)
        self.assertIn("bm25", only.source_tags)


class AgentRunnerDispatchTest(unittest.IsolatedAsyncioTestCase):
    """End-to-end: feed the runner a canned LLM plan, assert the right tool runs."""

    async def test_kb_lookup_dispatch_and_synthesis(self) -> None:
        """Model asks to look up 'AIS' → runner executes kb_lookup → model replies with text."""
        responses = [
            _tool_use_response(
                name="kb_lookup",
                tool_input={"query": "AIS", "top_k": 2},
            ),
            _text_response("AIS is the Annual Information Statement."),
        ]
        with patch(
            "itx_backend.agent.runner.llm_client.complete",
            new=AsyncMock(side_effect=responses),
        ):
            runner = AgentRunner()
            result = await runner.run(thread_id="t1", user_message="what is AIS?")

        self.assertIn("Annual Information Statement", result["content"])
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertEqual(result["tool_calls"][0]["name"], "kb_lookup")
        self.assertFalse(result["tool_calls"][0]["is_error"])
        # The runner took 2 steps: tool_use then final text.
        self.assertEqual(result["steps"], 2)

    async def test_portal_nav_dispatch(self) -> None:
        responses = [
            _tool_use_response(name="portal_nav", tool_input={"destination": "file_itr"}),
            _text_response("Go to e-File → Income Tax Returns → File Income Tax Return."),
        ]
        with patch(
            "itx_backend.agent.runner.llm_client.complete",
            new=AsyncMock(side_effect=responses),
        ):
            runner = AgentRunner()
            result = await runner.run(thread_id="t1", user_message="where do I file ITR")

        self.assertEqual(result["tool_calls"][0]["name"], "portal_nav")
        self.assertFalse(result["tool_calls"][0]["is_error"])
        # The tool result rides along for downstream consumers (e.g. chat service proposal extraction).
        self.assertIn("result", result["tool_calls"][0])
        self.assertIn("eportal.incometax.gov.in", result["tool_calls"][0]["result"]["url"])

    async def test_unknown_tool_surfaces_as_error(self) -> None:
        """If the model hallucinates a tool, the runner returns is_error=True and the turn
        continues — it does not crash."""
        responses = [
            _tool_use_response(name="nonexistent_tool", tool_input={}),
            _text_response("Sorry, I couldn't do that."),
        ]
        with patch(
            "itx_backend.agent.runner.llm_client.complete",
            new=AsyncMock(side_effect=responses),
        ):
            runner = AgentRunner()
            result = await runner.run(thread_id="t1", user_message="anything")

        self.assertTrue(result["tool_calls"][0]["is_error"])
        self.assertIn("content", result)

    async def test_invalid_tool_arguments_surface_as_error(self) -> None:
        """Bad kwargs produce TypeError-based tool errors, not crashes."""
        responses = [
            _tool_use_response(name="portal_nav", tool_input={"not_a_real_arg": "x"}),
            _text_response("I need the destination arg."),
        ]
        with patch(
            "itx_backend.agent.runner.llm_client.complete",
            new=AsyncMock(side_effect=responses),
        ):
            runner = AgentRunner()
            result = await runner.run(thread_id="t1", user_message="nav somewhere")

        self.assertTrue(result["tool_calls"][0]["is_error"])
        self.assertIn("invalid_tool_arguments", str(result["tool_calls"][0].get("result") or {}))

    async def test_no_tool_path_returns_direct_answer(self) -> None:
        """Small-talk / trivial messages should be answerable without any tool call."""
        responses = [_text_response("Hello! How can I help with your taxes today?")]
        with patch(
            "itx_backend.agent.runner.llm_client.complete",
            new=AsyncMock(side_effect=responses),
        ):
            runner = AgentRunner()
            result = await runner.run(thread_id="t1", user_message="hi")

        self.assertEqual(result["tool_calls"], [])
        self.assertIn("Hello", result["content"])
        self.assertEqual(result["steps"], 1)

    async def test_step_cap_truncates_gracefully(self) -> None:
        """Model stuck calling tools forever → runner bails with a terse message, not a crash."""
        # Keep returning tool_use for every step; runner should hit the step cap.
        response = _tool_use_response(name="how_to", tool_input={"query": "x"})
        with patch("itx_backend.agent.runner.llm_client.complete", new=AsyncMock(return_value=response)):
            runner = AgentRunner()
            result = await runner.run(thread_id="t1", user_message="spin")

        self.assertIn("tool-call budget", result["content"])
        self.assertTrue(result["metadata"].get("truncated"))


class ChatServiceProposalExtractionTest(unittest.TestCase):
    """Pure-function test of _extract_proposals — no DB, no LLM."""

    def test_picks_up_successful_propose_fill_with_proposal_id(self) -> None:
        from itx_backend.services.chat import ChatService

        service = ChatService()
        tool_calls = [
            {
                "name": "propose_fill",
                "input": {"page_type": "salary-schedule"},
                "is_error": False,
                "result": {
                    "proposal_id": "pid-1",
                    "approval_key": "fill:pid-1",
                    "status": "awaiting_approval",
                    "total_actions": 3,
                    "pages": [{"page_type": "salary-schedule", "actions": []}],
                },
            }
        ]
        proposals = service._extract_proposals(tool_calls)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["proposal_id"], "pid-1")
        self.assertEqual(proposals[0]["approval_key"], "fill:pid-1")

    def test_drops_nothing_to_fill_results(self) -> None:
        from itx_backend.services.chat import ChatService

        service = ChatService()
        tool_calls = [
            {
                "name": "propose_fill",
                "input": {},
                "is_error": False,
                "result": {"proposal_id": None, "status": "nothing_to_fill"},
            }
        ]
        self.assertEqual(service._extract_proposals(tool_calls), [])

    def test_ignores_errored_calls(self) -> None:
        from itx_backend.services.chat import ChatService

        service = ChatService()
        tool_calls = [
            {
                "name": "propose_fill",
                "input": {},
                "is_error": True,
                "result": {"error": "no_tax_facts"},
            }
        ]
        self.assertEqual(service._extract_proposals(tool_calls), [])


class PortalContextFlatteningTest(unittest.TestCase):
    def test_flattens_nested_portal_state_and_aliases_camel_case(self) -> None:
        from itx_backend.services.portal_context import portal_context_service

        merged = portal_context_service._flatten_context(
            {
                "page": "salary-schedule",
                "portal_state": {
                    "currentUrl": "https://eportal.incometax.gov.in/...",
                    "pageTitle": "Salary",
                    "fields": [{"id": "gross", "value": 1200000}],
                    "validationErrors": [{"field": "gross", "message": "required"}],
                },
            }
        )
        self.assertEqual(merged["current_url"], "https://eportal.incometax.gov.in/...")
        self.assertEqual(merged["page_title"], "Salary")
        self.assertEqual(len(merged["fields"]), 1)
        self.assertEqual(len(merged["errors"]), 1)

    def test_flat_shape_passes_through(self) -> None:
        from itx_backend.services.portal_context import portal_context_service

        merged = portal_context_service._flatten_context(
            {
                "current_url": "https://x",
                "fields": [{"id": "a"}],
                "errors": [],
            }
        )
        self.assertEqual(merged["current_url"], "https://x")
        self.assertEqual(len(merged["fields"]), 1)


if __name__ == "__main__":
    unittest.main()
