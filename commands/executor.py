"""
Executes a command by looking up its handler in the registry.
"""

import json

from .registry import REGISTRY


def run(command: str, arg: str) -> dict:
    """
    Execute a registered command.
    Returns a dict with "command" plus one of: image, text, data, error.
    """
    entry = REGISTRY.get(command)
    if entry is None:
        print(f"[Executor] Unknown command: {command!r}")
        return {"command": command, "error": f"Unknown command: {command}"}

    print(f"[Executor] Running {command!r} with arg={arg!r}")
    try:
        result = entry["handler"](arg)
    except Exception as exc:
        print(f"[Executor] {command!r} raised an exception: {exc}")
        result = {"error": str(exc)}

    if "error" in result:
        print(f"[Executor] {command!r} failed: {result['error']}")
    else:
        keys = [k for k in result if k != "image"]  # skip base64 blob
        print(f"[Executor] {command!r} succeeded — result keys={keys}")
        if "data" in result:
            print(f"[Executor] {command!r} data={json.dumps(result['data'], ensure_ascii=False, indent=2)}")
        elif "text" in result:
            print(f"[Executor] {command!r} text={result['text']!r}")

    result["command"] = command
    return result
