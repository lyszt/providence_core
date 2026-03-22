"""
Executes a classified command and returns a structured result dict.
Shared by the dispatch view and any view that reads needs_command=true.
"""

from . import math_tools


def run(command: str, arg: str) -> dict:
    """
    Execute a command by name with its argument string.

    Returns a dict that always includes at least one of:
      "image"  — base64 PNG
      "text"   — plain-text result
      "data"   — structured data (college info)
      "error"  — error message string
    Plus "command" echoed back for the caller.
    """
    result = _dispatch(command, arg)
    result["command"] = command
    return result


def _dispatch(command: str, arg: str) -> dict:
    # ------------------------------------------------------------------ math
    if command == "fx":
        return math_tools.graph_2d(arg)

    if command == "fxy":
        return math_tools.graph_3d(arg)

    if command == "simplify":
        return math_tools.math_simplify(arg)

    if command == "expand":
        return math_tools.math_expand(arg)

    if command == "factor":
        return math_tools.math_factor(arg)

    if command == "to_image":
        return math_tools.math_to_image(arg)

    if command == "solve":
        parts = [p.strip() for p in arg.split(",", 1)]
        expr = parts[0]
        var = parts[1] if len(parts) > 1 else "x"
        return math_tools.math_solve(expr, var)

    if command == "diff":
        parts = [p.strip() for p in arg.split(",", 1)]
        expr = parts[0]
        var = parts[1] if len(parts) > 1 else "x"
        return math_tools.math_diff(expr, var)

    if command == "integrate":
        parts = [p.strip() for p in arg.split(",")]
        expr = parts[0]
        var = parts[1] if len(parts) > 1 else "x"
        lower = parts[2] if len(parts) > 2 else None
        upper = parts[3] if len(parts) > 3 else None
        return math_tools.math_integrate(expr, var, lower, upper)

    if command == "limit":
        parts = [p.strip() for p in arg.split(",")]
        expr = parts[0]
        var = parts[1] if len(parts) > 1 else "x"
        point = parts[2] if len(parts) > 2 else "0"
        return math_tools.math_limit(expr, var, point)

    if command == "det":
        return math_tools.matrix_det(arg)

    if command == "inv":
        return math_tools.matrix_inv(arg)

    if command == "eigenvals":
        return math_tools.matrix_eigenvals(arg)

    # --------------------------------------------------------- college / SIGAA
    if command == "get_college_information":
        try:
            from . import sigaa
            data = sigaa.get_curriculum()
            return {"data": data}
        except RuntimeError as exc:
            return {"error": str(exc)}
        except ImportError as exc:
            return {"error": f"SIGAA scraper dependencies not installed: {exc}"}

    return {"error": f"Unknown command: {command}"}
