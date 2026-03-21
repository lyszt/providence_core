"""
Boot-time endpoint tests for Providence Core.

Run automatically via `make run` before the server starts.
Covers routing, input validation, and environment health.
Live API calls are limited to /speech/answer/ (cheap, single Gemini call).
/speech/deepthink/ is only checked for routing — not invoked due to cost.
"""

import json
import os
from pathlib import Path

from django.test import SimpleTestCase


class HealthCheckTest(SimpleTestCase):
    """Fast pre-flight checks — no API calls, no DB access."""

    def test_gemini_api_key_configured(self):
        key = os.environ.get("GEMINI_API_KEY", "")
        self.assertTrue(key, "GEMINI_API_KEY is not set or empty in environment")

    def test_cpp_binary_exists(self):
        binary = (
            Path(__file__).parent
            / "context_manager"
            / "Kievan Rus"
            / "kievan_rus_thinker"
        )
        self.assertTrue(binary.exists(), f"C++ binary missing: {binary}")
        self.assertTrue(os.access(binary, os.X_OK), f"C++ binary not executable: {binary}")

    def test_graph_output_dir_writable(self):
        graphs_dir = Path(__file__).parent / "context_manager" / "graphs"
        graphs_dir.mkdir(parents=True, exist_ok=True)
        self.assertTrue(graphs_dir.is_dir(), f"Graphs directory could not be created: {graphs_dir}")
        self.assertTrue(os.access(graphs_dir, os.W_OK), f"Graphs directory not writable: {graphs_dir}")


class AnswerEndpointTest(SimpleTestCase):
    """Tests for POST /speech/answer/ — one live Gemini call per live test."""

    def test_get_returns_405(self):
        response = self.client.get("/speech/answer/")
        self.assertEqual(response.status_code, 405)

    def test_missing_prompt_returns_400(self):
        response = self.client.post(
            "/speech/answer/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_empty_prompt_returns_400(self):
        response = self.client.post(
            "/speech/answer/",
            data=json.dumps({"prompt": "   "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_valid_prompt_returns_response(self):
        response = self.client.post(
            "/speech/answer/",
            data=json.dumps({"prompt": "Reply with only the word: pong"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertIn("response", data, "Response JSON missing 'response' key")
        self.assertIsInstance(data["response"], str)
        self.assertGreater(len(data["response"]), 0, "Response text was empty")

    def test_response_does_not_exceed_max_chars(self):
        response = self.client.post(
            "/speech/answer/",
            data=json.dumps({"prompt": "Say hi in one sentence."}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertLessEqual(len(response.json()["response"]), 4080)


class DeepThinkRoutingTest(SimpleTestCase):
    """
    Routing-only checks for POST /speech/deepthink/.
    No actual invocation — the full pipeline is expensive.
    """

    def test_get_returns_405(self):
        response = self.client.get("/speech/deepthink/")
        self.assertEqual(response.status_code, 405)

    def test_put_returns_405(self):
        response = self.client.put("/speech/deepthink/")
        self.assertEqual(response.status_code, 405)
