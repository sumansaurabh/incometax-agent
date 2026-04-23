from __future__ import annotations

import unittest
from unittest.mock import patch

from itx_backend.config import settings
from itx_backend.services.startup_health import StartupHealthService


class StartupHealthServiceTest(unittest.TestCase):
    def test_observability_does_not_require_generic_ai_api_key(self) -> None:
        service = StartupHealthService()

        with (
            patch(
                "itx_backend.services.startup_health.get_trace_status",
                return_value={"backend": "fallback", "exporter": "none"},
            ),
            patch.object(settings, "langfuse_enabled", False),
            patch.object(settings, "ai_provider", "openai"),
            patch.object(settings, "ai_model", "gpt-4.1-mini"),
            patch.object(settings, "ai_api_key", ""),
        ):
            result = service._check_observability()

        self.assertEqual(result["status"], "ok")
        self.assertIn("ai_provider=openai", result["detail"])
        self.assertIn("ai_model=gpt-4.1-mini", result["detail"])
        self.assertNotIn("ITX_AI_API_KEY is required", result["detail"])

    def test_observability_still_validates_langfuse_requirements(self) -> None:
        service = StartupHealthService()

        with (
            patch(
                "itx_backend.services.startup_health.get_trace_status",
                return_value={"backend": "fallback", "exporter": "none"},
            ),
            patch.object(settings, "langfuse_enabled", True),
            patch.object(settings, "langfuse_public_key", ""),
            patch.object(settings, "langfuse_secret_key", ""),
            patch.object(settings, "langfuse_otlp_endpoint", ""),
            patch.object(settings, "otel_exporter_otlp_endpoint", ""),
            patch.object(settings, "ai_provider", ""),
            patch.object(settings, "ai_model", ""),
            patch.object(settings, "ai_api_key", ""),
        ):
            result = service._check_observability()

        self.assertEqual(result["status"], "failed")
        self.assertIn("langfuse public/secret keys are required", result["detail"])
        self.assertIn("langfuse OTLP endpoint is required", result["detail"])