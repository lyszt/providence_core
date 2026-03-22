"""
Command classifier — determines whether a user prompt maps to a known command
and extracts the argument for it.

Used by both /commands/dispatch/ and the deep_think view when Kievan Rus
flags needs_command=true.
"""

from google import genai
from pydantic import BaseModel

CAPABILITIES_PROMPT = """
[ YOUR CAPABILITIES ]
You are Clairemont, the emperor's assistant. Beyond conversation, you can execute the following commands when a user's request calls for it:

  Graphing:
    - fx              : plot a single-variable function as a 2D graph (e.g. "plot sin(x)/x")
    - fxy             : plot a two-variable function as a 3D surface (e.g. "show me x²+y²")

  Algebra:
    - simplify        : simplify a mathematical expression
    - expand          : expand a polynomial
    - factor          : factor an expression into irreducible parts
    - solve           : solve an equation for a variable (default x)
    - to_image        : render any math expression as a LaTeX image

  Calculus:
    - diff            : differentiate an expression with respect to a variable
    - integrate       : compute indefinite or definite integrals
    - limit           : evaluate a limit as a variable approaches a point

  Matrix algebra:
    - det             : determinant of a matrix
    - inv             : inverse of a square matrix
    - eigenvals       : eigenvalues of a square matrix

  University portal:
    - get_college_information : fetch the student's current disciplines, schedule,
                                and upcoming assignments from the SIGAA portal

When a user's request clearly calls for one of the above, you should invoke the appropriate command rather than describing what it would do.
""".strip()

COMMANDS: dict[str, str] = {
    "fx": "Generate a 2D plot of a single-variable mathematical function.",
    "fxy": "Generate a 3D plot of a two-variable mathematical function.",
    "get_college_information": "Retrieve the user's course, current disciplines, and upcoming assignments from the university portal (SIGAA).",
    "simplify": "Simplify a mathematical expression.",
    "expand": "Expand a polynomial expression.",
    "factor": "Factor an expression into its irreducible factors.",
    "solve": "Solve an equation for a variable (default: x). Input the expression set equal to zero.",
    "diff": "Differentiate an expression with respect to a variable (default: x).",
    "integrate": "Compute the indefinite or definite integral of an expression.",
    "limit": "Calculate the limit of an expression as a variable approaches a point.",
    "det": "Calculate the determinant of a matrix. Input as a list of lists, e.g. [[1,2],[3,4]].",
    "inv": "Calculate the inverse of a square matrix.",
    "eigenvals": "Find the eigenvalues of a square matrix.",
    "to_image": "Render a mathematical expression as a LaTeX image.",
}


class CommandDecision(BaseModel):
    command: str
    arg: str


def classify(prompt: str) -> dict:
    """
    Classify a natural-language prompt.

    Returns {"command": str, "arg": str}.
    command is "None" (string) if no command was matched.
    """
    client = genai.Client()
    commands_block = "\n".join(f'  "{k}": "{v}"' for k, v in COMMANDS.items())

    content = f"""You are an intelligent command classifier for an AI assistant server.

Analyze the user's message and decide:
1. Whether it clearly maps to one of the known commands below.
2. If so, extract or infer the appropriate argument string.

Available commands:
{commands_block}

Rules:
- Return the exact command key if matched, or "None" if no command fits.
- For math expressions, use Python syntax: ** for powers, * for multiplication (e.g. 3*x not 3x).
- For matrix operations, format the arg as a Python list of lists: [[1,2],[3,4]].
- For integrate, if bounds are given include them in arg as "expr, x, lower, upper".
- For limit, format arg as "expr, x, point".
- For solve and diff, format arg as "expr" or "expr, var".
- For get_college_information, the arg should be an empty string.
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
