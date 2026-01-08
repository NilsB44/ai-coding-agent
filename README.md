# 🤖 Local AI Coding Agent

An autonomous coding assistant that runs locally using **Ollama (Llama 3)**.

## 🚀 Setup & Run (The Right Way)

1.  **Start Ollama** (if not running):
    ```bash
    ollama serve
    # If it says "address already in use", you are good!
    ```

2.  **Setup Environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # <--- CRITICAL STEP
    pip install -r requirements.txt
    ```

3.  **Run Agent**:
    ```bash
    python agent/main.py
    ```
