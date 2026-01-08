# 🤖 Local AI Coding Agent

An autonomous coding assistant that runs locally using **Ollama (Llama 3)**. It reads Python files, plans changes using structured JSON, and applies code updates safely.

## 🌟 Features
* **Local Inference**: Runs 100% offline using Llama 3 via Ollama.
* **Structured Outputs**: Uses `Pydantic` to force the LLM to return valid JSON plans, not just chatty text.
* **Safety "Immune System"**: Validates all generated code using Python's `ast` (Abstract Syntax Tree) module before saving to disk.
* **Idempotent Operations**: Designed to modify specific files in a sandboxed environment.

## 🛠️ Tech Stack
* **Python 3.12**
* **Ollama** (Inference Server)
* **OpenAI SDK** (Client wrapper)
* **Pydantic** (Data validation)

## 🚀 Setup

1.  **Prerequisites:**
    * Install [Ollama](https://ollama.com/) and pull the model:
        ```bash
        ollama pull llama3
        ```

2.  **Installation:**
    ```bash
    git clone [https://github.com/NilsB44/ai-coding-agent.git](https://github.com/NilsB44/ai-coding-agent.git)
    cd ai-coding-agent
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **Configuration:**
    Create a `.env` file (if using OpenAI, otherwise optional for local):
    ```text
    OPENAI_API_KEY=ollama  # Placeholder for local use
    ```

## 🏃 Usage

1.  Ensure Ollama is running (`ollama serve`).
2.  Run the agent:
    ```bash
    python agent/main.py
    ```
3.  The agent will target files in the `sandbox/` directory.

## 🛡️ Safety Mechanisms
The agent uses a **Validator** step that parses the Abstract Syntax Tree (AST) of any generated code. If the LLM generates syntax errors (e.g., missing colons, bad indentation), the change is rejected automatically.
