"""
Boot-time tests for Providence Core.

Run automatically via `make run` before the server starts.
Checks environment variables, API key validity, database connectivity,
binary presence, and endpoint routing — without reading .env directly.

Test classes:
  EnvironmentTest     - env vars present, .env file exists (not read)
  ApiKeyTest          - Gemini key actually works (1 minimal API call)
  DatabaseTest        - DB credentials present + TCP connectivity
  AnswerEndpointTest  - routing + input validation + 1 live answer call
  DeepThinkRoutingTest - routing only (no invocation — pipeline is costly)
"""

import json
import os
from pathlib import Path

import psycopg2
from django.test import SimpleTestCase
from google import genai


BASE_DIR = Path(__file__).resolve().parent.parent


class EnvironmentTest(SimpleTestCase):
    """Check that all required environment variables are loaded and the .env file exists."""

    def test_dotenv_file_exists(self):
        env_path = BASE_DIR / ".env"
        self.assertTrue(env_path.exists(), f".env file not found at {env_path}")

    def test_gemini_api_key_present(self):
        self.assertTrue(
            os.environ.get("GEMINI_API_KEY", "").strip(),
            "GEMINI_API_KEY is missing or empty in environment",
        )

    def test_secret_key_present(self):
        self.assertTrue(
            os.environ.get("SECRET_KEY", "").strip(),
            "SECRET_KEY is missing or empty in environment",
        )

    def test_db_credentials_present(self):
        missing = [
            var for var in ("DB_NAME", "DB_USER", "DB_PASSWORD")
            if not os.environ.get(var, "").strip()
        ]
        self.assertFalse(missing, f"Missing DB environment variables: {missing}")

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
        self.assertTrue(graphs_dir.is_dir())
        self.assertTrue(os.access(graphs_dir, os.W_OK), f"Graphs dir not writable: {graphs_dir}")


class ApiKeyTest(SimpleTestCase):
    """Verify the Gemini API key is valid by making the cheapest possible call."""

    def test_gemini_api_key_works(self):
        try:
            client = genai.Client()
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents="Reply with exactly one word: ok",
            )
            self.assertTrue(
                response.text.strip(),
                "Gemini returned an empty response — key may be valid but quota exhausted",
            )
        except Exception as exc:
            self.fail(f"Gemini API call failed (key likely invalid or quota exceeded): {exc}")


class DatabaseTest(SimpleTestCase):
    """Check DB credentials and verify a TCP connection can be opened."""

    def _db_params(self):
        return {
            "dbname": os.environ.get("DB_NAME"),
            "user": os.environ.get("DB_USER"),
            "password": os.environ.get("DB_PASSWORD"),
            "host": os.environ.get("DB_HOST", "localhost"),
            "port": os.environ.get("DB_PORT", "5432"),
            "connect_timeout": 5,
        }

    def test_database_connection(self):
        params = self._db_params()
        missing = [k for k, v in params.items() if v is None]
        if missing:
            self.fail(f"Cannot test DB — missing env vars: {missing}")
        try:
            conn = psycopg2.connect(**params)
            conn.close()
        except psycopg2.OperationalError as exc:
            self.fail(f"Database connection failed: {exc}")


class AnswerEndpointTest(SimpleTestCase):
    """Tests for POST /speech/answer/ — routing, validation, and one live call."""

    databases = ("default",)

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
            data=json.dumps({"prompt": "Reply with only the word: pong", "username": "test:test"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertIn("response", data)
        self.assertIsInstance(data["response"], str)
        self.assertGreater(len(data["response"]), 0)

    def test_response_does_not_exceed_max_chars(self):
        response = self.client.post(
            "/speech/answer/",
            data=json.dumps({"prompt": "Say hi in one sentence.", "username": "test:test"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertLessEqual(len(response.json()["response"]), 4080)


class DeepThinkRoutingTest(SimpleTestCase):
    """
    Routing-only checks for POST /speech/deepthink/.
    No invocation — the full ThinkingManager pipeline is too costly for boot tests.
    """

    def test_get_returns_405(self):
        response = self.client.get("/speech/deepthink/")
        self.assertEqual(response.status_code, 405)

    def test_put_returns_405(self):
        response = self.client.put("/speech/deepthink/")
        self.assertEqual(response.status_code, 405)
