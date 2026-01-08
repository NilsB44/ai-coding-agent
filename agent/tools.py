import ast
import difflib

def read_file(filepath: str):
    with open(filepath, 'r') as f:
        return f.read()

def validate_python_code(code: str) -> tuple[bool, str]:
    """
    Validates Python code syntax using AST (Abstract Syntax Tree).
    Returns: (is_valid, error_message)
    """
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"Syntax Error on line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Validation Error: {str(e)}"

def show_diff(original: str, proposed: str):
    """
    Prints a colored diff between the original and proposed strings.
    """
    diff = difflib.unified_diff(
        original.splitlines(),
        proposed.splitlines(),
        fromfile='Original',
        tofile='Proposed',
        lineterm=''
    )
    
    print("\n👀 Review Changes:")
    for line in diff:
        if line.startswith('+') and not line.startswith('+++'):
            print(f"\033[92m{line}\033[0m")  # Green for additions
        elif line.startswith('-') and not line.startswith('---'):
            print(f"\033[91m{line}\033[0m")  # Red for deletions
        else:
            print(line)