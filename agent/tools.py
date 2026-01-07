def read_file(filepath: str):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    # Return line numbers so the LLM knows where to edit!
    return "".join([f"{i+1}: {line}" for i, line in enumerate(lines)])
