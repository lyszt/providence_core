"""
Single source of truth for all Providence commands.

Each entry defines:
  category    — used to group entries in the capabilities prompt
  description — used by the Gemini classifier to understand when to invoke the command
  example     — optional natural-language trigger shown in the capabilities prompt
  arg_hint    — optional formatting hint shown to the classifier
  handler     — callable(arg: str) -> dict, the actual implementation

Adding a new command means adding one entry here. Nothing else needs to change.
"""

from collections import defaultdict
from . import math_tools


# ---------------------------------------------------------------------------
# Argument parsers shared by multi-param commands
# ---------------------------------------------------------------------------

def _two(arg: str, default: str = "x"):
    parts = [p.strip() for p in arg.split(",", 1)]
    return parts[0], parts[1] if len(parts) > 1 else default


def _three(arg: str, default_var: str = "x", default_point: str = "0"):
    parts = [p.strip() for p in arg.split(",")]
    expr = parts[0]
    var = parts[1] if len(parts) > 1 else default_var
    point = parts[2] if len(parts) > 2 else default_point
    return expr, var, point


def _four(arg: str, default_var: str = "x"):
    parts = [p.strip() for p in arg.split(",")]
    expr = parts[0]
    var = parts[1] if len(parts) > 1 else default_var
    lower = parts[2] if len(parts) > 2 else None
    upper = parts[3] if len(parts) > 3 else None
    return expr, var, lower, upper


def _college_handler(_arg: str) -> dict:
    try:
        from . import sigaa
        return {"data": sigaa.get_curriculum()}
    except RuntimeError as exc:
        return {"error": str(exc)}
    except ImportError as exc:
        return {"error": f"SIGAA dependencies not installed: {exc}"}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

REGISTRY: dict[str, dict] = {
    # — Graphing ——————————————————————————————————————————————————————————————
    "fx": {
        "category": "Graphing",
        "description": "Generate a 2D plot of a single-variable mathematical function.",
        "example": "plot sin(x)/x",
        "arg_hint": "the function expression, e.g. sin(x)/x",
        "handler": lambda arg: math_tools.graph_2d(arg),
    },
    "fxy": {
        "category": "Graphing",
        "description": "Generate a 3D surface plot of a two-variable mathematical function.",
        "example": "show me x²+y²",
        "arg_hint": "the function expression, e.g. x**2 + y**2",
        "handler": lambda arg: math_tools.graph_3d(arg),
    },

    # — Algebra ———————————————————————————————————————————————————————————————
    "simplify": {
        "category": "Algebra",
        "description": "Simplify a mathematical expression.",
        "handler": lambda arg: math_tools.math_simplify(arg),
    },
    "expand": {
        "category": "Algebra",
        "description": "Expand a polynomial expression.",
        "handler": lambda arg: math_tools.math_expand(arg),
    },
    "factor": {
        "category": "Algebra",
        "description": "Factor an expression into its irreducible parts.",
        "handler": lambda arg: math_tools.math_factor(arg),
    },
    "solve": {
        "category": "Algebra",
        "description": "Solve an equation for a variable (default x). Pass expression set equal to zero.",
        "arg_hint": "expr  or  expr, var",
        "handler": lambda arg: math_tools.math_solve(*_two(arg, "x")),
    },
    "to_image": {
        "category": "Algebra",
        "description": "Render any mathematical expression as a LaTeX image.",
        "handler": lambda arg: math_tools.math_to_image(arg),
    },

    # — Calculus ——————————————————————————————————————————————————————————————
    "diff": {
        "category": "Calculus",
        "description": "Differentiate an expression with respect to a variable (default x).",
        "arg_hint": "expr  or  expr, var",
        "handler": lambda arg: math_tools.math_diff(*_two(arg, "x")),
    },
    "integrate": {
        "category": "Calculus",
        "description": "Compute the indefinite or definite integral of an expression.",
        "arg_hint": "expr  or  expr, var  or  expr, var, lower, upper",
        "handler": lambda arg: math_tools.math_integrate(*_four(arg, "x")),
    },
    "limit": {
        "category": "Calculus",
        "description": "Evaluate the limit of an expression as a variable approaches a point.",
        "arg_hint": "expr, var, point",
        "handler": lambda arg: math_tools.math_limit(*_three(arg, "x", "0")),
    },

    # — Matrix algebra ————————————————————————————————————————————————————————
    "det": {
        "category": "Matrix algebra",
        "description": "Calculate the determinant of a matrix.",
        "arg_hint": "matrix as a list of lists, e.g. [[1,2],[3,4]]",
        "handler": lambda arg: math_tools.matrix_det(arg),
    },
    "inv": {
        "category": "Matrix algebra",
        "description": "Calculate the inverse of a square matrix.",
        "arg_hint": "matrix as a list of lists",
        "handler": lambda arg: math_tools.matrix_inv(arg),
    },
    "eigenvals": {
        "category": "Matrix algebra",
        "description": "Find the eigenvalues of a square matrix.",
        "arg_hint": "matrix as a list of lists",
        "handler": lambda arg: math_tools.matrix_eigenvals(arg),
    },

    # — University portal —————————————————————————————————————————————————————
    "get_college_information": {
        "category": "University portal",
        "description": "Fetch the student's current disciplines, schedule, and upcoming assignments from the SIGAA portal.",
        "arg_hint": "(no argument needed)",
        "handler": _college_handler,
    },
}


# ---------------------------------------------------------------------------
# Derived constants — import these everywhere instead of duplicating
# ---------------------------------------------------------------------------

COMMAND_NAMES: frozenset[str] = frozenset(REGISTRY.keys())


def _build_capabilities_prompt() -> str:
    by_category: dict[str, list] = defaultdict(list)
    for name, entry in REGISTRY.items():
        by_category[entry["category"]].append((name, entry))

    lines = [
        "[ YOUR CAPABILITIES ]",
        "You are Clairemont, the emperor's assistant. Beyond conversation, you can",
        "execute the following commands when a user's request calls for it.",
        "",
        "When a user's request clearly maps to a command, output ONLY the exact",
        "command name on its own line (e.g. get_college_information). The server",
        "will detect it and execute it automatically — do NOT describe what you",
        "would do, just output the command name.",
        "",
    ]
    for category, entries in by_category.items():
        lines.append(f"  {category}:")
        for name, entry in entries:
            example = entry.get("example", "")
            suffix = f'  — e.g. "{example}"' if example else ""
            lines.append(f"    - {name:<28} {entry['description']}{suffix}")
        lines.append("")

    return "\n".join(lines).strip()


CAPABILITIES_PROMPT: str = _build_capabilities_prompt()


def _build_classifier_prompt() -> str:
    """Compact description for the Gemini classifier (dispatcher.py)."""
    lines = []
    for name, entry in REGISTRY.items():
        hint = entry.get("arg_hint", "")
        hint_str = f"  [arg: {hint}]" if hint else ""
        lines.append(f'  "{name}": "{entry["description"]}"{hint_str}')
    return "\n".join(lines)


CLASSIFIER_COMMAND_BLOCK: str = _build_classifier_prompt()
