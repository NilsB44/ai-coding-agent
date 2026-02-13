import ast
import difflib
import os
import subprocess
import sys
import shutil
import time
import concurrent.futures
from typing import Any, Optional, List, Tuple


def read_file(filepath: str) -> str:
    """Reads a file and returns its content."""
    try:
        with open(filepath) as f:
            return f.read()
    except FileNotFoundError:
        return ""


def get_file_tree(directory: str = "sandbox") -> str:
    """
    Scans the sandbox directory and returns a summary of all files
    and their defined functions/classes.
    """
    summary = []

    if not os.path.exists(directory):
        return "Directory not found."

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath) as f:
                        content = f.read()
                    tree = ast.parse(content)

                    definitions = []
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            definitions.append(f"def {node.name}(...)")
                        elif isinstance(node, ast.ClassDef):
                            definitions.append(f"class {node.name}")

                    summary.append(f"📄 {file}:")
                    if definitions:
                        summary.append("   " + "\n   ".join(definitions))
                    else:
                        summary.append("   (No definitions)")
                    summary.append("")

                except Exception:
                    summary.append(f"📄 {file} (Could not parse)")

    return "\n".join(summary)


def validate_python_code(code: str) -> tuple[bool, str]:
    """
    Validates Python code syntax using AST.
    Returns: (is_valid, error_message_with_context)
    """
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        error_line = e.text.strip() if e.text else "Unknown Code"
        error_msg = (
            f"Syntax Error on line {e.lineno}: {e.msg}\n"
            f"OFFENDING CODE: >> {error_line} <<\n"
            "Requirement: Ensure indentation is 4 spaces and brackets match."
        )
        return False, error_msg
    except Exception as e:
        return False, f"Validation Error: {str(e)}"


def show_diff(original: str, proposed: str) -> None:
    """
    Prints a colored diff between the original and proposed strings.
    """
    diff = difflib.unified_diff(
        original.splitlines(), proposed.splitlines(), fromfile="Original", tofile="Proposed", lineterm=""
    )

    print("\n👀 Review Changes:")
    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            print(f"\033[92m{line}\033[0m")  # Green
        elif line.startswith("-") and not line.startswith("---"):
            print(f"\033[91m{line}\033[0m")  # Red
        else:
            print(line)


def run_pytest(test_file: str, workdir: Optional[str] = None) -> tuple[bool, str]:
    """
    Runs pytest on a specific file and returns (success, output).
    """
    try:
        env = os.environ.copy()
        current_dir = workdir if workdir else os.getcwd()
        env["PYTHONPATH"] = current_dir

        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_file],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
            cwd=current_dir
        )
        return (result.returncode == 0, result.stdout + result.stderr)
    except Exception as e:
        return (False, f"Test Execution Failed: {str(e)}")


def parse_llm_response(response: str) -> dict[str, Any]:
    """
    Extracts code blocks and thought process from raw LLM text.
    """
    result = {
        "thought_process": "",
        "action": "overwrite",
        "new_code": "",
        "test_code": "",
    }

    if "THOUGHT:" in response:
        # Improved extraction to handle various formats
        parts = response.split("THOUGHT:")
        if len(parts) > 1:
            thought_part = parts[1]
            if "CODE:" in thought_part:
                result["thought_process"] = thought_part.split("CODE:")[0].strip()
            elif "```python" in thought_part:
                result["thought_process"] = thought_part.split("```python")[0].strip()
            else:
                result["thought_process"] = thought_part.strip()

    import re
    # Extract all python blocks
    code_blocks = re.findall(r"```python(.*?)```", response, re.DOTALL)

    if len(code_blocks) >= 1:
        result["new_code"] = code_blocks[0].strip()

    if len(code_blocks) >= 2:
        result["test_code"] = code_blocks[1].strip()

    return result


class WorktreeManager:
    """Manages git worktrees for isolated agent environments."""
    
    def __init__(self, base_repo_path: str):
        self.base_path = os.path.abspath(base_repo_path)
        self.worktrees_root = os.path.join(self.base_path, ".agent_worktrees")
        if not os.path.exists(self.worktrees_root):
            os.makedirs(self.worktrees_root)

    def create_worktree(self, name: str) -> str:
        """Creates a new git worktree for an agent."""
        wt_path = os.path.join(self.worktrees_root, name)
        if os.path.exists(wt_path):
            self.cleanup_worktree(name)
            
        branch_name = f"agent-{name}-{int(time.time())}"
        
        try:
            # Create a new branch and worktree
            subprocess.run(
                ["git", "worktree", "add", "-b", branch_name, wt_path, "main"],
                cwd=self.base_path,
                check=True,
                capture_output=True
            )
            return wt_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create worktree: {e.stderr.decode()}")

    def cleanup_worktree(self, name: str) -> None:
        """Removes a git worktree and its branch."""
        wt_path = os.path.join(self.worktrees_root, name)
        if not os.path.exists(wt_path):
            return

        try:
            subprocess.run(["git", "worktree", "remove", "--force", wt_path], cwd=self.base_path, capture_output=True)
            # Find the branch associated with this worktree and delete it if needed
            # (Git 2.17+ removes the branch automatically if it was created with worktree add -b)
        except Exception as e:
            print(f"Warning: Cleanup failed for {wt_path}: {e}")
        finally:
            if os.path.exists(wt_path):
                shutil.rmtree(wt_path, ignore_errors=True)

    def cleanup_all(self) -> None:
        """Removes all agent worktrees."""
        if os.path.exists(self.worktrees_root):
            for item in os.listdir(self.worktrees_root):
                self.cleanup_worktree(item)


class ParallelValidator:
    """Runs multiple validation tasks in parallel."""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    def run_validations(self, tasks: List[Tuple[Any, Any]]) -> List[Any]:
        """
        Executes a list of (function, args) tasks in parallel.
        Returns the list of results.
        """
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {executor.submit(func, *args): i for i, (func, args) in enumerate(tasks)}
            for future in concurrent.futures.as_completed(future_to_task):
                results.append(future.result())
        return results
