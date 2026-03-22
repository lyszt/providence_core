"""
Executes a command by looking up its handler in the registry.
"""

from .registry import REGISTRY


def run(command: str, arg: str) -> dict:
    """
    Execute a registered command.
    Returns a dict with "command" plus one of: image, text, data, error.
    """
    entry = REGISTRY.get(command)
    if entry is None:
        return {"command": command, "error": f"Unknown command: {command}"}
    result = entry["handler"](arg)
    result["command"] = command
    return result
