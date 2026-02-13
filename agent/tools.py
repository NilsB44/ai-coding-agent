import ast
import difflib
import os
import subprocess
import sys


def read_file(filepath: str):
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
        # e.text usually contains the specific line that failed
        error_line = e.text.strip() if e.text else "Unknown Code"

        # Build a helpful error message
        error_msg = (
            f"Syntax Error on line {e.lineno}: {e.msg}\n"
            f"OFFENDING CODE: >> {error_line} <<\n"
            "Requirement: Ensure indentation is 4 spaces and brackets match."
        )
        return False, error_msg
    except Exception as e:
        return False, f"Validation Error: {str(e)}"


def show_diff(original: str, proposed: str):
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


def run_pytest(test_file: str) -> tuple[bool, str]:
    """
    Runs pytest on a specific file and returns (success, output).
    """
    try:
        # Add current directory to PYTHONPATH so imports work
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()

        # Run pytest
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_file], capture_output=True, text=True, timeout=10, env=env
        )
        return (result.returncode == 0, result.stdout + result.stderr)
    except Exception as e:
        return (False, f"Test Execution Failed: {str(e)}")


def parse_llm_response(response: str) -> dict:
    """
    Extracts code blocks and thought process from raw LLM text.
    Expected format:
    THOUGHT: ...
    FILE: ...
    CODE:
    ```python
    ...
    ```
    """
    result = {
        "thought_process": "",
        "action": "overwrite",  # Default to safe overwrite
        "new_code": "",
        "test_code": "",
    }

    # 1. Extract Thought
    if "THOUGHT:" in response:
        result["thought_process"] = response.split("THOUGHT:")[1].split("FILE:")[0].strip()

    # 2. Extract Code (Look for python blocks)
    import re

    code_blocks = re.findall(r"```python(.*?)```", response, re.DOTALL)

    if len(code_blocks) >= 1:
        result["new_code"] = code_blocks[0].strip()

    if len(code_blocks) >= 2:
        result["test_code"] = code_blocks[1].strip()

    return result
