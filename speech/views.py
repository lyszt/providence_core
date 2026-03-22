import json
import os

from django.shortcuts import render  # noqa: F401

from .context_manager.ThinkingManager import ThinkingManager
from .gemini import agent as gemini_agent
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from commands.dispatcher import classify
from commands.executor import run as run_command
from commands.registry import CAPABILITIES_PROMPT, COMMAND_NAMES

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

    # Catch: if the final response is a bare command name, run the command,
    # then add a new ThinkingManager node with the result so the tree can
    # rethink and produce a proper answer.
    detected_cmd = response.strip().rstrip("()").strip()
    if detected_cmd in COMMAND_NAMES:
        decision = classify(prompt)
        cmd_arg = decision.get("arg", "") if decision.get("command") == detected_cmd else ""
        result = run_command(detected_cmd, cmd_arg)

        if "error" in result:
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if "data" in result:
            result_summary = json.dumps(result["data"], ensure_ascii=False, indent=2)
        elif "text" in result:
            result_summary = result["text"]
        else:
            result_summary = result.get("label", detected_cmd)

        # New node: rethink with the command result as context
        followup_node = ThinkingManager(
            message=prompt,
            previous=manager,
            summarized_thought=(
                f"Command '{detected_cmd}' was executed. Result:\n{result_summary}\n"
                "Now reason about how to answer the user using this result."
            ),
            branch_label="Command-Result",
            max_depth=0,
        )
        followup_prompt = followup_node.generate_self_prompt()

        final_instructions = (
            f"{CAPABILITIES_PROMPT}\n\n"
            "Answer directly. You are in a chat environment.\n"
            f"{followup_prompt}"
        )

        try:
            verbal = agent.generate_response("gemini-2.5-flash", final_instructions).text
            if len(verbal) > MAX_CHARS:
                verbal = verbal[:MAX_CHARS - 12] + "\n\n[truncated]"
            result["response"] = verbal
        except Exception as error:
            return Response({"error": str(error)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(result, status=status.HTTP_200_OK)

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

    # Catch: if the model responded with a bare command name, run it and
    # feed the result back into a new Gemini node for a natural response.
    detected_cmd = response.strip().rstrip("()").strip()
    if detected_cmd in COMMAND_NAMES:
        decision = classify(prompt)
        cmd_arg = decision.get("arg", "") if decision.get("command") == detected_cmd else ""
        result = run_command(detected_cmd, cmd_arg)

        if "error" in result:
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Image or structured data — return directly with a verbal commentary node
        if "image" in result or "data" in result:
            if "data" in result:
                summary = json.dumps(result["data"], ensure_ascii=False, indent=2)
            else:
                summary = result.get("label", detected_cmd)

            verbal_instructions = (
                f"{CAPABILITIES_PROMPT}\n\n"
                "Your name is Clairemont. You are the emperor's assistant.\n"
                f"You just executed the command '{detected_cmd}'. Here is its result:\n"
                f"{summary}\n"
                "Provide a brief, natural verbal commentary. Do not repeat raw data."
            )
            try:
                verbal = agent.generate_response("gemini-2.5-flash-lite", verbal_instructions).text
                if len(verbal) > MAX_CHARS:
                    verbal = verbal[:MAX_CHARS - 12] + "\n\n[truncated]"
                result["response"] = verbal
            except Exception:
                result["response"] = None
            return Response(result, status=status.HTTP_200_OK)

        # Text result — weave it into a natural response
        result_text = result.get("text", str(result))
        follow_up = (
            f"{CAPABILITIES_PROMPT}\n\n"
            "Your name is Clairemont. You are the emperor's assistant.\n"
            f"You just ran '{detected_cmd}' and the result is: {result_text}\n"
            f"Original user prompt: {prompt}\n"
            "Respond naturally, incorporating the result."
        )
        try:
            response = agent.generate_response("gemini-2.5-flash-lite", follow_up).text
        except Exception as error:
            return Response({"error": str(error)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if len(response) > MAX_CHARS:
        response = response[:MAX_CHARS - 12] + "\n\n[truncated]"

    return Response({"response": response}, status=status.HTTP_200_OK)
