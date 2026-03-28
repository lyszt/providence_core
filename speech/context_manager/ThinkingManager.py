import datetime
import json
import os
import struct
import subprocess
import tempfile
import uuid
import textwrap
from pathlib import Path
from typing import Any, Optional, Tuple
import matplotlib

from pydantic import BaseModel, Field

from plotting.graphing import ThoughtNode, render_thought_graph


class ContextStruct(BaseModel):
    user_enquiry: str = Field(
        description="The raw, unaltered text query received from the user."
    )
    user_name: str = Field(
        description="The display name or identifier for the user who sent the query."
    )
    needs_command: bool = Field(
        description="A flag indicating if the query requires an external tool or command to be executed."
    )
    client_platform: str = Field(
        description="The source application the query originated from."
    )
    category: str = Field(
        description="The general classification or topic of the user's enquiry."
    )
    steps_for_completion: str = Field(
        description="The high-level plan or steps generated for the AI agent to follow."
    )
    possible_setbacks: str = Field(
        default="",
        description="Enumerate the risks, trade-offs, or downsides for the current plan.",
    )
    probability_of_success: float = Field(
        default=0.0,
        description="Likelihood (0.0-1.0) that this branch succeeds.",
    )
    potential_score: float = Field(
        default=0.0,
        description="Incremental potential score contributed by this branch.",
    )
    date_of_request: datetime.datetime = Field(
        default_factory=datetime.datetime.now,
        description="The timestamp marking when this context object was created."
    )
    is_done_thinking: bool = Field(
        description="Are these enough steps of thought or should we continue?"
    )
    regrets_choice: bool = Field(
        description="Are you going the right way? Should you return back to a previous step?"
    )


class ThinkingProcessError(RuntimeError):
    """Raised when the C++ thinking process reports an error or fails."""


CPP_DIR = Path(__file__).resolve().parent / "Kievan Rus"
CPP_BINARY_NAME = "kievan_rus_thinker"
if os.name == "nt":
    CPP_BINARY_NAME += ".exe"
CPP_BINARY = CPP_DIR / CPP_BINARY_NAME


def _locate_env_file() -> Optional[Path]:
    """Return the most likely .env file path, if it exists."""
    explicit = os.environ.get("KIEVAN_RUS_ENV_PATH")
    if explicit:
        candidate = Path(explicit)
        if candidate.exists():
            return candidate
    project_root = Path(__file__).resolve().parents[2]
    default_env = project_root / ".env"
    if default_env.exists():
        return default_env
    return None


def _ensure_cpp_binary() -> Path:
    """
    Ensure the C++ assistant is compiled. If the binary is missing or older than
    the source file, attempt to rebuild it. This assumes a system compiler and libcurl.
    """
    try:
        sources = sorted(CPP_DIR.glob("*.cpp"))
        headers = list(CPP_DIR.glob("*.hpp"))
    except OSError as exc:
        raise ThinkingProcessError(f"Unable to enumerate C++ sources: {exc}") from exc

    if not sources:
        raise ThinkingProcessError("No C++ source files found for the thinking engine.")

    latest_timestamp = 0.0
    for path in sources + headers:
        try:
            latest_timestamp = max(latest_timestamp, path.stat().st_mtime)
        except OSError:
            continue

    if CPP_BINARY.exists():
        try:
            if CPP_BINARY.stat().st_mtime >= latest_timestamp:
                return CPP_BINARY
        except OSError:
            pass

    compile_command = [
        "g++",
        "-std=c++17",
        "-O2",
        *[path.name for path in sources],
        "-lcurl",
        "-o",
        str(CPP_BINARY),
    ]

    try:
        subprocess.run(
            compile_command,
            check=True,
            cwd=str(CPP_DIR),
        )
    except FileNotFoundError as exc:
        raise ThinkingProcessError(
            "C++ compiler (g++) not found. Install a C++17-compatible compiler to build the thinking engine."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise ThinkingProcessError(
            f"Failed to compile C++ thinking engine. Command: {' '.join(compile_command)}"
        ) from exc

    return CPP_BINARY


def _read_binary_payload(path: Path) -> Tuple[dict[str, Any], str]:
    """
    The binary payload is encoded as:
        status (1 byte)
        context_length (4 bytes, big-endian)
        context payload (context_length bytes, UTF-8)
        summary_length (4 bytes, big-endian)
        summary payload (summary_length bytes, UTF-8)
    """
    with path.open("rb") as stream:
        status_raw = stream.read(1)
        if len(status_raw) != 1:
            raise ThinkingProcessError("Malformed output from C++ thinking engine (missing status byte).")

        status = status_raw[0]

        context_len_bytes = stream.read(4)
        if len(context_len_bytes) != 4:
            raise ThinkingProcessError("Malformed output from C++ thinking engine (missing context length).")
        context_length = struct.unpack(">I", context_len_bytes)[0]
        context_payload = stream.read(context_length)
        if len(context_payload) != context_length:
            raise ThinkingProcessError("Malformed output from C++ thinking engine (truncated context payload).")

        summary_len_bytes = stream.read(4)
        if len(summary_len_bytes) != 4:
            raise ThinkingProcessError("Malformed output from C++ thinking engine (missing summary length).")
        summary_length = struct.unpack(">I", summary_len_bytes)[0]
        summary_payload = stream.read(summary_length)
        if len(summary_payload) != summary_length:
            raise ThinkingProcessError("Malformed output from C++ thinking engine (truncated summary payload).")

    context_text = context_payload.decode("utf-8")
    summary_text = summary_payload.decode("utf-8")

    if status != 0:
        raise ThinkingProcessError(context_text or "C++ thinking engine reported an error.")

    try:
        context_obj = json.loads(context_text)
    except json.JSONDecodeError as exc:
        raise ThinkingProcessError("Unable to parse JSON generated by C++ thinking engine.") from exc

    if not isinstance(context_obj, dict):
        raise ThinkingProcessError("Unexpected JSON structure from C++ thinking engine.")

    return context_obj, summary_text


def _invoke_cpp_thinker(
    message: str,
    iteration: int,
    summarized_thought: str,
    branch_label: str,
) -> Tuple[dict[str, Any], str]:
    binary_path = _ensure_cpp_binary()
    env_path = _locate_env_file()

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        output_path = Path(tmp.name)

    command = [
        str(binary_path),
        "--message",
        message,
        "--output",
        str(output_path),
        "--iteration",
        str(iteration),
    ]
    if summarized_thought:
        command.extend(["--summary", summarized_thought])
    if branch_label:
        command.extend(["--branch", branch_label])
    if env_path:
        command.extend(["--env", str(env_path)])

    try:
        subprocess.run(command, check=True, cwd=str(CPP_DIR))
        return _read_binary_payload(output_path)
    except subprocess.CalledProcessError as exc:
        raise ThinkingProcessError(
            f"C++ thinking engine execution failed with exit code {exc.returncode}."
        ) from exc
    finally:
        try:
            output_path.unlink(missing_ok=True)
        except AttributeError:
            if output_path.exists():
                output_path.unlink()


class ThinkingManager:
    def __init__(
        self,
        message,
        iteration: int = 0,
        previous: Optional["ThinkingManager"] = None,
        summarized_thought: str = "",
        branch_label: str = "Primary",
        max_depth: int = 2,
    ):
        self.next = []
        self.id = str(uuid.uuid4())
        self.graph_path: Optional[Path] = None
        self.branch_label = branch_label
        self.summary_text = summarized_thought
        self.max_depth = max_depth
        self.probability_of_success: float = 0.0
        self.potential_increment: float = 0.0
        self.cumulative_potential: float = (
            previous.cumulative_potential if previous is not None else 0.0
        )

        self.previous = previous
        if previous is not None:
            previous.next.append(self)

        self.message = message
        self.iteration = iteration + 1
        self.max_iterations = 8

        try:
            raw_context, summarize_thought = _invoke_cpp_thinker(
                message=message,
                iteration=self.iteration,
                summarized_thought=summarized_thought,
                branch_label=self.branch_label,
            )
        except ThinkingProcessError as exc:
            print(f"Error running C++ thinking engine: {exc}")
            self.context = None
            return

        try:
            command_obj = ContextStruct.model_validate(raw_context)
        except Exception as exc:
            print(f"Validation error parsing context: {exc}")
            self.context = None
            return

        self.context = command_obj.model_dump()
        self.summary_text = summarize_thought or self.summary_text

        self.probability_of_success = self._to_float(
            self.context.get("probability_of_success"),
            default=0.0,
            clamp=(0.0, 1.0),
        )
        self.potential_increment = self._to_float(
            self.context.get("potential_score"),
            default=0.0,
        )
        self.cumulative_potential += self.potential_increment

        self.context["probability_of_success"] = self.probability_of_success
        self.context["potential_increment"] = self.potential_increment
        self.context["potential_score"] = self.potential_increment
        self.context["cumulative_potential"] = self.cumulative_potential
        self.context["branch_label"] = self.branch_label

        self._log(
            f"Evaluated branch '{self.branch_label}' (ID: {self.id}) | "
            f"Prob: {self.probability_of_success:.2f} | "
            f"ΔPotential: {self.potential_increment:+.2f} | "
            f"Cumulative: {self.cumulative_potential:.2f}"
        )

        should_spawn = False
        if self.previous is None and self.iteration <= self.max_iterations:
            should_spawn = True
        elif (
            not self.context.get("is_done_thinking", False)
            and self.iteration <= self.max_iterations
        ):
            should_spawn = True

        if should_spawn:
            self._spawn_branch_children(
                message=message,
                base_summary=self.summary_text,
            )

    @staticmethod
    def _log(message: str) -> None:
        print(f"[ThinkingManager] {message}")

    @staticmethod
    def _to_float(value: Any, default: float = 0.0, clamp: Optional[Tuple[float, float]] = None) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return default

        if clamp is not None:
            low, high = clamp
            if low is not None:
                result = max(low, result)
            if high is not None:
                result = min(high, result)
        return result

    @staticmethod
    def _wrap_label(text: str, width: int = 42) -> str:
        if not text:
            return "No content"
        return textwrap.fill(" ".join(text.split()), width=width)

    def _spawn_branch_children(self, message: str, base_summary: str) -> None:
        if self.iteration >= self.max_iterations:
            self._log("Maximum iteration reached; skipping branch expansion.")
            return

        if getattr(self, "_branches_created", False):
            self._log("Branches already created for this node; skipping additional expansion.")
            return

        # Only spawn branches for the root node (Primary) and first-level branches
        # Count depth by checking how many branch segments exist
        # Primary → 0 levels deep (create branches)
        # A, B (or Primary-A, Primary-B) → 1 level deep (create branches)
        # A-A, A-B, B-A, B-B → 2 levels deep (stop here)

        # Calculate branch depth based on label structure
        if self.branch_label == "Primary":
            branch_depth = 0
        else:
            # Remove "Primary-" prefix if it exists for counting
            label_to_check = self.branch_label.replace("Primary-", "")
            # Count number of segments separated by hyphens
            branch_depth = len(label_to_check.split("-"))

        if branch_depth >= self.max_depth:
            self._log(f"Branch '{self.branch_label}' is at depth {branch_depth} (max {self.max_depth}); stopping expansion.")
            return

        branch_suffixes = ["A", "B"]
        for index, suffix in enumerate(branch_suffixes, start=1):
            child_label = f"{self.branch_label}-{suffix}".strip("-")
            augmented_summary = (base_summary or "").strip()
            branch_summary = (
                f"{augmented_summary}\nBranch {child_label}: explore an alternate path distinct from other branches. "
                f"Parent cumulative potential: {self.cumulative_potential:.2f}. "
                f"Focus on a unique strategy with a quantified probability of success."
            ).strip()

            self._log(
                f"Spawning branch '{child_label}' from parent '{self.branch_label}' (ID: {self.id})."
            )

            ThinkingManager(
                message=message,
                iteration=self.iteration,
                previous=self,
                summarized_thought=branch_summary,
                branch_label=child_label,
                max_depth=self.max_depth,
            )

        self._branches_created = True

    def _collect_graph_data(self):
        self._log("Collecting thought graph data for rendering.")
        root = self
        while root.previous is not None:
            root = root.previous

        nodes: list[ThoughtNode] = []
        edges: list[tuple[str, str]] = []
        stack: list[tuple["ThinkingManager", int, Optional[str]]] = [(root, 0, None)]
        visited: set[str] = set()

        while stack:
            node, depth, parent_id = stack.pop()
            if node.id in visited or node.context is None:
                self._log(f"Skipping node {node.id} (visited or missing context).")
                continue
            visited.add(node.id)

            plan_text = node.context.get("steps_for_completion", "No plan generated.")
            setbacks = node.context.get("possible_setbacks", "")
            probability = self._to_float(
                node.context.get("probability_of_success"),
                default=0.0,
                clamp=(0.0, 1.0),
            )
            potential_increment = self._to_float(
                node.context.get("potential_increment", node.context.get("potential_score")),
                default=0.0,
            )
            cumulative_potential = self._to_float(
                node.context.get("cumulative_potential"),
                default=getattr(node, "cumulative_potential", 0.0),
            )
            branch_label = node.context.get("branch_label", getattr(node, "branch_label", "Branch"))

            detail_parts = [plan_text]
            if setbacks:
                detail_parts.append(f"Setbacks: {setbacks}")
            combined_label = "\n".join(detail_parts)

            nodes.append(
                ThoughtNode(
                    id=node.id,
                    depth=depth,
                    label=self._wrap_label(combined_label),
                    branch_label=branch_label,
                    probability=probability,
                    potential_increment=potential_increment,
                    cumulative_potential=cumulative_potential,
                    is_final=bool(node.context.get("is_done_thinking")),
                    regrets=bool(node.context.get("regrets_choice")),
                )
            )

            if parent_id is not None:
                edges.append((parent_id, node.id))
                self._log(f"Registered edge {parent_id} -> {node.id}.")

            for child in reversed(node.next):
                stack.append((child, depth + 1, node.id))

        self._log(f"Collected {len(nodes)} nodes and {len(edges)} edges for graph.")
        return nodes, edges, root

    def _render_thought_graph(self) -> Optional[Path]:
        try:
            nodes, edges, root = self._collect_graph_data()
        except Exception as exc:
            self._log(f"Unable to collect thought graph data: {exc}")
            return None

        if not nodes:
            self._log("No nodes available for thought graph rendering.")
            return None

        if getattr(root, "_graph_cached_path", None):
            self._log("Using cached thought graph path.")
            return root._graph_cached_path  # type: ignore[attr-defined]

        graphs_dir = Path(__file__).resolve().parent / "graphs"
        output_path = graphs_dir / f"thought_graph_{root.id}.png"

        try:
            self._log(f"Rendering thought graph to {output_path}.")
            render_thought_graph(nodes, edges, output_path)
            self._log(f"Thought graph successfully saved to {output_path}.")
        except RuntimeError as exc:
            self._log(f"Unable to render thought graph: {exc}")
            return None
        except Exception as exc:
            self._log(f"Unexpected error rendering thought graph: {exc}")
            return None

        setattr(root, "_graph_cached_path", output_path)
        return output_path

    def build_thought_tree_prompt(self) -> str:
        """
        Builds a text representation of the entire thought process
        by traversing up to the root, then recursively printing the tree.
        """

        root = self
        while root.previous is not None:
            root = root.previous

        output_lines = []
        self._build_tree_recursive(root, 0, output_lines)
        print("\n".join(output_lines))
        return "\n".join(output_lines)

    def _build_tree_recursive(self, node: "ThinkingManager", depth: int, output_lines: list):
        """
        Recursively traverses the thought tree and build the string.
        """
        if node.context is None:
            return

        indent = "  " * depth
        plan = node.context.get("steps_for_completion", "No plan generated.")
        setbacks = node.context.get("possible_setbacks", "")
        regrets = node.context.get("regrets_choice", False)
        branch_label = node.context.get("branch_label", getattr(node, "branch_label", "Branch"))
        probability = self._to_float(
            node.context.get("probability_of_success"),
            default=0.0,
            clamp=(0.0, 1.0),
        )
        potential_increment = self._to_float(
            node.context.get("potential_increment", node.context.get("potential_score")),
            default=0.0,
        )
        cumulative_potential = self._to_float(
            node.context.get("cumulative_potential"),
            default=getattr(node, "cumulative_potential", 0.0),
        )

        prefix = ""
        if regrets:
            prefix = "[REGRETTED] "
        elif node.context.get("is_done_thinking", False):
            prefix = "[FINAL] "

        detail_parts = [f"Branch: {branch_label}", f"Plan: {plan}"]
        if setbacks:
            detail_parts.append(f"Setbacks: {setbacks}")
        detail_parts.append(f"Prob={probability:.2f}")
        detail_parts.append(f"ΔPotential={potential_increment:+.2f}")
        detail_parts.append(f"Cumulative={cumulative_potential:.2f}")
        detail = " | ".join(detail_parts)

        output_lines.append(f"{indent}{prefix}Thought (ID: {node.id}, Depth: {depth}): {detail}")

        for child_node in node.next:
            self._build_tree_recursive(child_node, depth + 1, output_lines)

    def generate_self_prompt(self):
        thought_tree_string = self.build_thought_tree_prompt()

        root = self
        while root.previous is not None:
            root = root.previous
        original_user_message = root.message

        """
        FOR TESTING
        graph_path = self._render_thought_graph()
        if graph_path is not None:
            self.graph_path = graph_path
            self._log(f"Graph path stored on manager: {graph_path}")
        """

        return f"""
        [ ORIGINAL USER MESSAGE ]
        {original_user_message}

        [ I need to respond to this user. ]
        [ Here is my complete thought process on how to answer: ]
        {thought_tree_string}

        [ Based on this plan, provide the final response. Follow the *last* thought. ]
        """
