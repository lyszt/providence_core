"""
Command classifier — uses Gemini to map a natural-language prompt to a
registry command name + argument string.
"""

from google import genai
from pydantic import BaseModel

from .registry import CLASSIFIER_COMMAND_BLOCK, COMMAND_NAMES


class CommandDecision(BaseModel):
    command: str
    arg: str


def classify(prompt: str) -> dict:
    """
    Returns {"command": str, "arg": str}.
    command is "None" (string) if no command matched.
    """
    client = genai.Client()
    content = f"""You are an intelligent command classifier for an AI assistant server.

Analyze the user's message and decide:
1. Whether it clearly maps to one of the known commands below.
2. If so, extract or infer the appropriate argument string.

Available commands:
{CLASSIFIER_COMMAND_BLOCK}

Rules:
- Return the exact command key if matched, or "None" if nothing fits.
- Math expressions must use Python syntax (** for powers, * for multiplication).
- Matrix args must be formatted as a Python list of lists: [[1,2],[3,4]].
- For get_college_information the arg must be an empty string.
- If the user asks you to pick (e.g. "show me something cool"), choose a sensible default.

User message: "{prompt}"
"""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config={
                "response_mime_type": "application/json",
                "response_schema": CommandDecision,
            },
            contents=content,
        )
        return CommandDecision.model_validate_json(response.text).model_dump()
    except Exception:
        return {"command": "None", "arg": ""}
