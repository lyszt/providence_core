import json
import os

from django.shortcuts import render

from .context_manager.ThinkingManager import ThinkingManager
from .gemini import agent as gemini_agent
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from commands.dispatcher import classify, CAPABILITIES_PROMPT
from commands.executor import run as run_command

MAX_CHARS = 4080

@api_view(['POST'])
def deep_think(request):
    """
    Deep thinking view: runs the ThinkingManager to produce a final response.

    Optional body fields:
      light (bool) — when true, runs a single-node Kievan Rus call with no
                     branching (max_depth=0). Much cheaper; good for moderate
                     queries that still benefit from structured context.
    """
    prompt = str(request.data.get('prompt', '')).strip()
    if not prompt:
        return Response({"error": "No prompt provided."}, status=status.HTTP_400_BAD_REQUEST)

    light = bool(request.data.get('light', False))
    max_depth = 0 if light else 2

    manager = ThinkingManager(message=prompt, max_depth=max_depth)
    self_prompt = manager.generate_self_prompt()

    # Check if Kievan Rus flagged that a command is needed.
    # Walk to root node and inspect its context.
    root = manager
    while root.previous is not None:
        root = root.previous
    needs_command = (
        root.context.get("needs_command", False) if root.context else False
    )

    command_block = ""
    if needs_command:
        decision = classify(prompt)
        cmd = decision.get("command", "None")
        if cmd and cmd != "None":
            result = run_command(cmd, decision.get("arg", ""))
            if "error" not in result:
                # Summarise the command result as text for the final prompt
                if "data" in result:
                    import json
                    summary = json.dumps(result["data"], ensure_ascii=False, indent=2)
                elif "text" in result:
                    summary = result["text"]
                elif "label" in result:
                    summary = f"Graph produced: {result['label']}"
                else:
                    summary = str(result)
                command_block = (
                    f"\n[ COMMAND EXECUTED: {cmd} ]\n"
                    f"[ RESULT ]\n{summary}\n"
                    f"[ Use this result in your final answer. ]\n"
                )
                # For image/data responses, return the command result directly
                # alongside the AI response rather than burying it in text.
                if "image" in result or "data" in result:
                    result["command"] = cmd
                    result["needs_command"] = True
                    # Still generate a short verbal response
                    agent = gemini_agent.GeminiAgent()
                    verbal_instructions = (
                        f"{CAPABILITIES_PROMPT}\n\n"
                        "Answer directly. You are in a chat environment.\n"
                        f"{self_prompt}{command_block}"
                        "Provide a brief verbal commentary on the command result. "
                        "Do not repeat raw data — just interpret or acknowledge it."
                    )
                    try:
                        verbal = agent.generate_response("gemini-2.5-flash", verbal_instructions).text
                        if len(verbal) > MAX_CHARS:
                            verbal = verbal[:MAX_CHARS - 12] + "\n\n[truncated]"
                        result["response"] = verbal
                    except Exception:
                        result["response"] = None
                    return Response(result, status=status.HTTP_200_OK)

    agent = gemini_agent.GeminiAgent()
    instructions = (
        f"{CAPABILITIES_PROMPT}\n\n"
        "Answer directly. You are in a chat environment.\n"
        f"{self_prompt}{command_block}"
    )

    try:
        response = agent.generate_response("gemini-2.5-flash", instructions).text
    except Exception as error:
        return Response({"error": str(error)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if len(response) > MAX_CHARS:
        response = response[:MAX_CHARS - 12] + "\n\n[truncated]"

    return Response({"response": response}, status=status.HTTP_200_OK)


@api_view(['POST'])
def simple_response(request):
    """
    Lightweight simple response view: directly queries Gemini with the provided prompt
    and returns the text without invoking the ThinkingManager.
    """
    prompt = str(request.data.get('prompt', '')).strip()
    if not prompt:
        return Response({"error": "No prompt provided."}, status=status.HTTP_400_BAD_REQUEST)

    agent = gemini_agent.GeminiAgent()

    instructions = (
        f"{CAPABILITIES_PROMPT}\n\n"
        "Your name is Clairemont. You are the emperor's assistant. Answer the user's prompt directly and concisely.\n"
        f"User prompt: {prompt}\n"
        "Provide only the answer text, no extra metadata."
    )

    try:
        response = agent.generate_response("gemini-2.5-flash-lite", instructions).text
    except Exception as error:
        return Response({"error": str(error)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if len(response) > MAX_CHARS:
        response = response[:MAX_CHARS - 12] + "\n\n[truncated]"

    return Response({"response": response}, status=status.HTTP_200_OK)
