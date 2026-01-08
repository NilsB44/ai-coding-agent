import ast

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
