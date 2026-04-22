from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from itx_workers.document_pipeline import process_document


def load_case_bank(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("cases", []))


def _read_dotted(value: dict[str, Any], dotted_path: str) -> Any:
    current: Any = value
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _values_equal(expected: Any, actual: Any) -> bool:
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) < 1e-6
    return expected == actual


async def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    processed = await process_document(dict(case.get("payload", {})))
    expected = case.get("expected", {})
    checks: list[dict[str, Any]] = []

    if "document_type" in expected:
        actual_document_type = processed.get("document_type")
        checks.append(
            {
                "field": "document_type",
                "expected": expected["document_type"],
                "actual": actual_document_type,
                "passed": _values_equal(expected["document_type"], actual_document_type),
            }
        )

    if "parser" in expected:
        actual_parser = processed.get("parsed", {}).get("parser")
        checks.append(
            {
                "field": "parser",
                "expected": expected["parser"],
                "actual": actual_parser,
                "passed": _values_equal(expected["parser"], actual_parser),
            }
        )

    normalized_fields = processed.get("normalized_fields", {})
    for field_path, expected_value in expected.get("normalized_fields", {}).items():
        actual_value = _read_dotted(normalized_fields, field_path)
        checks.append(
            {
                "field": field_path,
                "expected": expected_value,
                "actual": actual_value,
                "passed": _values_equal(expected_value, actual_value),
            }
        )

    passed_check_count = sum(1 for check in checks if check["passed"])
    parser_name = str(processed.get("parsed", {}).get("parser", "unknown"))
    return {
        "case_id": case.get("case_id", "unknown"),
        "parser": parser_name,
        "document_type": processed.get("document_type"),
        "check_count": len(checks),
        "passed_check_count": passed_check_count,
        "passed": passed_check_count == len(checks),
        "checks": checks,
        "processing_summary": processed.get("processing_summary", {}),
    }


async def build_scorecard(cases: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = []
    for case in cases:
        evaluated.append(await evaluate_case(case))

    total_checks = sum(item["check_count"] for item in evaluated)
    passed_checks = sum(item["passed_check_count"] for item in evaluated)
    failed_cases = [item["case_id"] for item in evaluated if not item["passed"]]

    parsers: dict[str, dict[str, Any]] = {}
    for item in evaluated:
        parser_name = item["parser"]
        summary = parsers.setdefault(
            parser_name,
            {
                "case_count": 0,
                "check_count": 0,
                "passed_check_count": 0,
                "failed_cases": [],
            },
        )
        summary["case_count"] += 1
        summary["check_count"] += item["check_count"]
        summary["passed_check_count"] += item["passed_check_count"]
        if not item["passed"]:
            summary["failed_cases"].append(item["case_id"])

    for summary in parsers.values():
        summary["coverage"] = (
            float(summary["passed_check_count"]) / float(summary["check_count"])
            if summary["check_count"]
            else 0.0
        )

    return {
        "totals": {
            "case_count": len(evaluated),
            "failed_cases": len(failed_cases),
            "check_count": total_checks,
            "passed_check_count": passed_checks,
            "field_coverage": float(passed_checks) / float(total_checks) if total_checks else 0.0,
        },
        "failed_case_ids": failed_cases,
        "parsers": parsers,
        "cases": evaluated,
    }