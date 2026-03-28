"""
Command endpoints for Providence.

POST /commands/dispatch/
    Classifies a natural-language prompt, runs the matched command,
    or falls through to a direct Gemini answer if no command matches.

POST /commands/math/
    Execute a math command directly (no classification step).

POST /commands/college/
    Fetch SIGAA university data directly.
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from speech.gemini import agent as gemini_agent
from .dispatcher import classify
from .registry import CAPABILITIES_PROMPT
from .executor import run
from authentication.models import User
from authentication.utils import authorize

@api_view(["POST"])
def dispatch(request):
    """
    Smart entry point: classify the prompt, execute the command if matched,
    or return a plain Gemini answer if the prompt is conversational.

    Request body:
        prompt  (str, required)

    Response always contains "command" (null if none matched) plus
    whichever of "image" / "text" / "data" / "response" / "error" apply.
    """
    prompt = str(request.data.get("prompt", "")).strip()
    if not prompt:
        return Response({"error": "No prompt provided."}, status=status.HTTP_400_BAD_REQUEST)

    decision = classify(prompt)
    command = decision.get("command", "None")
    arg = decision.get("arg", "")

    if command and command != "None":
        result = run(command, arg)
        if "error" in result:
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(result, status=status.HTTP_200_OK)

    # No command — fall back to a plain Gemini answer
    agent = gemini_agent.GeminiAgent()
    instructions = (
        f"{CAPABILITIES_PROMPT}\n\n"
        "Your name is Clairemont. You are the emperor's assistant. "
        "Answer the user's prompt directly and concisely.\n"
        f"User prompt: {prompt}\n"
        "Provide only the answer text, no extra metadata."
    )
    try:
        text = agent.generate_response("gemini-2.5-flash-lite", instructions).text
    except Exception as exc:
        return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS - 12] + "\n\n[truncated]"

    return Response({"command": None, "response": text}, status=status.HTTP_200_OK)


@api_view(["POST"])
def math(request):
    """
    Execute a math command directly.

    Request body:
        operation  (str, required) — one of: fx, fxy, simplify, expand, factor,
                   solve, diff, integrate, limit, det, inv, eigenvals, to_image
        expr       (str) — expression or matrix string
        var        (str, default "x") — variable for calculus operations
        point      (str, default "0") — point for limit
        lower      (str|null) — lower bound for definite integral
        upper      (str|null) — upper bound for definite integral
    """
    operation = str(request.data.get("operation", "")).strip()
    if not operation:
        return Response({"error": "No operation provided."}, status=status.HTTP_400_BAD_REQUEST)

    expr = str(request.data.get("expr", "")).strip()
    var = str(request.data.get("var", "x")).strip()
    point = str(request.data.get("point", "0")).strip()
    lower = request.data.get("lower")
    upper = request.data.get("upper")

    # Build the arg string the executor expects
    if operation == "integrate" and lower is not None and upper is not None:
        arg = f"{expr}, {var}, {lower}, {upper}"
    elif operation in ("solve", "diff"):
        arg = f"{expr}, {var}"
    elif operation == "limit":
        arg = f"{expr}, {var}, {point}"
    else:
        arg = expr

    result = run(operation, arg)
    if "error" in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result, status=status.HTTP_200_OK)


@api_view(["POST"])
def college(request):
    """
    Fetch university data from SIGAA.
    Credentials come from SIGAA_USER and SIGAA_PASS env vars.
    Takes an id and verifies if it is allowed to access my Sigaa information
    """

    username: str = str(request.data.get("username", "")).strip()
    if (err := authorize(username, User.PermissionFlags.ADMIN)):
        return err
    
    result = run("get_college_information", "")
    if "error" in result:
        return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return Response(result, status=status.HTTP_200_OK)
