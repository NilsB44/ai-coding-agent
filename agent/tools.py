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

def get_file_tree(directory: str = "sandbox") -> str:
    """
    Scans the sandbox directory and returns a summary of all files 
    and their defined functions/classes.
    """
    import os
    summary = []
    
    if not os.path.exists(directory):
        return "Directory not found."

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                
                # Read file and parse AST to get function definitions
                try:
                    with open(filepath, "r") as f:
                        content = f.read()
                    tree = ast.parse(content)
                    
                    # Extract function and class names
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
                    summary.append("") # Empty line for spacing
                    
                except Exception:
                    summary.append(f"📄 {file} (Could not parse)")

    return "\n".join(summary)