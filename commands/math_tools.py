"""
Math tools ported from clairemont_core.
All image-producing functions return base64-encoded PNG strings.
All functions return a dict — callers should check for an "error" key.
"""

import base64
import io
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sympy import (
    Matrix, SympifyError, diff, expand, factor, integrate, latex,
    lambdify, limit, simplify, solve, symbols, sympify,
)


# ---------------------------------------------------------------------------
# Expression preprocessing
# ---------------------------------------------------------------------------

def _prep(expr: str) -> str:
    """Normalise a human-typed expression to Python/SymPy syntax."""
    expr = expr.replace("^", "**").replace("²", "**2").replace("³", "**3")
    expr = re.sub(r"(\d)([a-zA-Z])", r"\1*\2", expr)
    return expr


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _sympy_to_image(sym_result) -> dict:
    """Render any SymPy result as a LaTeX PNG image."""
    try:
        latex_str = latex(sym_result)
    except Exception:
        latex_str = str(sym_result)

    fig, ax = plt.subplots(figsize=(max(2.5, len(latex_str) * 0.14), 1.2))
    ax.axis("off")
    ax.text(0.5, 0.5, f"${latex_str}$", size=22, ha="center", va="center")
    return {
        "image": _fig_to_b64(fig),
        "latex": latex_str,
        "text": str(sym_result),
    }


# ---------------------------------------------------------------------------
# Graphing
# ---------------------------------------------------------------------------

def graph_2d(expr: str) -> dict:
    expr = _prep(expr)
    x = symbols("x")
    try:
        func = sympify(expr)
        f = lambdify(x, func, modules=["numpy"])
        xs = np.linspace(-20, 20, 1000)
        ys = f(xs)
    except Exception as exc:
        return {"error": str(exc)}

    fig, ax = plt.subplots()
    ax.plot(xs, ys, color="black", linewidth=2)
    ax.set_title(f"f(x) = {expr}")
    ax.set_xlabel("x")
    ax.set_ylabel("f(x)")
    ax.grid(True)
    return {"image": _fig_to_b64(fig), "label": f"f(x) = {expr}"}


def graph_3d(expr: str) -> dict:
    expr = _prep(expr)
    x_sym, y_sym = symbols("x y")
    try:
        func = sympify(expr)
        f = lambdify((x_sym, y_sym), func, modules=["numpy"])
        xs = np.linspace(-10, 10, 100)
        ys = np.linspace(-10, 10, 100)
        X, Y = np.meshgrid(xs, ys)
        Z = f(X, Y)
    except Exception as exc:
        return {"error": str(exc)}

    fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(X, Y, Z, cmap="viridis")
    ax.set_title(f"f(x, y) = {expr}")
    return {"image": _fig_to_b64(fig), "label": f"f(x, y) = {expr}"}


# ---------------------------------------------------------------------------
# Algebra
# ---------------------------------------------------------------------------

def math_simplify(expr: str) -> dict:
    try:
        return _sympy_to_image(simplify(sympify(_prep(expr))))
    except (SympifyError, TypeError, SyntaxError) as exc:
        return {"error": str(exc)}


def math_expand(expr: str) -> dict:
    try:
        return _sympy_to_image(expand(sympify(_prep(expr))))
    except (SympifyError, TypeError, SyntaxError) as exc:
        return {"error": str(exc)}


def math_factor(expr: str) -> dict:
    try:
        return _sympy_to_image(factor(sympify(_prep(expr))))
    except (SympifyError, TypeError, SyntaxError) as exc:
        return {"error": str(exc)}


def math_solve(expr: str, var: str = "x") -> dict:
    try:
        var_sym = symbols(var)
        solutions = solve(sympify(_prep(expr)), var_sym)
        if not solutions:
            return {"text": "No solution found.", "result": []}
        latex_parts = []
        text_parts = []
        for r in solutions:
            try:
                latex_parts.append(latex(r))
            except Exception:
                latex_parts.append(str(r))
            text_parts.append(str(r))
        combined_latex = f"{var} \\in \\{{{', '.join(latex_parts)}\\}}"
        fig, ax = plt.subplots(figsize=(max(3, len(combined_latex) * 0.12), 1.2))
        ax.axis("off")
        ax.text(0.5, 0.5, f"${combined_latex}$", size=20, ha="center", va="center")
        return {
            "image": _fig_to_b64(fig),
            "latex": combined_latex,
            "text": f"{var} = {', '.join(text_parts)}",
        }
    except (SympifyError, TypeError, SyntaxError) as exc:
        return {"error": str(exc)}


def math_to_image(expr: str) -> dict:
    try:
        return _sympy_to_image(sympify(_prep(expr)))
    except (SympifyError, TypeError, SyntaxError) as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Calculus
# ---------------------------------------------------------------------------

def math_diff(expr: str, var: str = "x") -> dict:
    try:
        return _sympy_to_image(diff(sympify(_prep(expr)), symbols(var)))
    except (SympifyError, TypeError, SyntaxError) as exc:
        return {"error": str(exc)}


def math_integrate(expr: str, var: str = "x", lower=None, upper=None) -> dict:
    try:
        var_sym = symbols(var)
        parsed = sympify(_prep(expr))
        if lower is not None and upper is not None:
            result = integrate(parsed, (var_sym, sympify(str(lower)), sympify(str(upper))))
        else:
            result = integrate(parsed, var_sym)
        return _sympy_to_image(result)
    except (SympifyError, TypeError, SyntaxError) as exc:
        return {"error": str(exc)}


def math_limit(expr: str, var: str = "x", point: str = "0") -> dict:
    try:
        return _sympy_to_image(limit(sympify(_prep(expr)), symbols(var), sympify(point)))
    except (SympifyError, TypeError, SyntaxError) as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Matrix operations
# ---------------------------------------------------------------------------

def _to_matrix(matrix) -> Matrix:
    raw = matrix if isinstance(matrix, str) else str(matrix)
    return Matrix(sympify(raw))


def matrix_det(matrix) -> dict:
    try:
        mat = _to_matrix(matrix)
        result = mat.det()
        return {"text": str(result), "value": float(result) if result.is_number else str(result)}
    except Exception as exc:
        return {"error": str(exc)}


def matrix_inv(matrix) -> dict:
    try:
        mat = _to_matrix(matrix)
        if not mat.is_square:
            return {"error": "Matrix must be square to have an inverse."}
        if mat.det() == 0:
            return {"error": "Matrix is singular and has no inverse."}
        return _sympy_to_image(mat.inv())
    except Exception as exc:
        return {"error": str(exc)}


def matrix_eigenvals(matrix) -> dict:
    try:
        mat = _to_matrix(matrix)
        if not mat.is_square:
            return {"error": "Matrix must be square to find eigenvalues."}
        ev = mat.eigenvals()
        text = ", ".join(f"{k} (multiplicity {v})" for k, v in ev.items())
        return {"text": text, "eigenvalues": {str(k): int(v) for k, v in ev.items()}}
    except Exception as exc:
        return {"error": str(exc)}
