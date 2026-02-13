import glob
import os
import sys
from typing import Any, Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

# Import tools
from tools import parse_llm_response, read_file, run_pytest, show_diff, validate_python_code

load_dotenv()

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

# --- STRUCTURES ---


class FileSelection(BaseModel):
    thought_process: str = Field(description="Reasoning for why this file was chosen.")
    file_name: str = Field(description="The existing file to edit, or a new file name to create.")


class CodeUpdate(BaseModel):
    thought_process: str = Field(description="Analyze the request and explain what needs to be changed.")
    action: Literal["append", "replace", "overwrite"] = Field(description="Action to perform.")
    search_text: str | None = Field(description="Code to replace (for 'replace' action).")
    new_code: str = Field(description="The new code.")
    test_code: str | None = Field(description="A corresponding pytest unit test to verify this code works. (Optional)")


# --- STEP 1: ROUTER ---


def select_target_file(user_request: str) -> str:
    """Decides which file to edit based on the user request."""

    files = glob.glob("sandbox/*.py")
    file_list_str = "\n".join(files)

    system_prompt = f"""
    You are a Senior Technical Lead.
    Your job is to select the correct file to edit based on the user's request.
    
    Available Files:
    {file_list_str}
    
    INSTRUCTIONS:
    1. Select an existing file if possible.
    2. If the request requires a new file, provide a suitable name.
    3. ⚠️ IMPORTANT: All new files MUST be created inside the 'sandbox/' directory (e.g., 'sandbox/fibonacci.py').
    """

    print("🤔 Routing request to correct file...")
    try:
        completion = client.beta.chat.completions.parse(
            model="llama3",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_request},
            ],
            response_format=FileSelection,
        )
        result = completion.choices[0].message.parsed
        if result:
            print(f"📂 Selected File: {result.file_name} ({result.thought_process})")
            return result.file_name
        return "sandbox/error.py"
    except Exception as e:
        print(f"Routing Error: {e}")
        return "sandbox/error.py"


# --- STEP 2: SURGEON ---


def apply_changes(target_file: str, user_request: str) -> None:
    # --- FIX 1: Force Sandbox Path ---
    # If the router picked "fibonacci.py" (root), force it to "sandbox/fibonacci.py"
    if not target_file.startswith("sandbox/"):
        target_file = os.path.join("sandbox", target_file)
    # ---------------------------------

    print(f"🤖 Agent starting on: {target_file}")

    # Handle New Files
    if not os.path.exists(target_file):
        # Create directory if needed
        directory = os.path.dirname(target_file)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        with open(target_file, "w") as f:
            f.write("")
        current_content = ""
    else:
        current_content = read_file(target_file)

    # Calculate import name (e.g., "sandbox.math_lib")
    import_name = target_file.replace("/", ".").replace(".py", "")

    system_prompt = f"""
    You are a Python Coding Agent.
    
    CONTEXT:
    File: {target_file}
    Content:
    {current_content}
    
    INSTRUCTIONS:
    1. Write the new code for this file.
    2. Write a pytest unit test.
    
    IMPORTANT RULES:
    - **NO MARKDOWN**: Just write the code blocks.
    - **TEST IMPORTS**: You MUST import the function like this:
      `from {import_name} import function_name`
    
    FORMAT:
    THOUGHT: <explain your plan>
    CODE:
    ```python
    # The FULL new content of {target_file}
    ```
    TEST:
    ```python
    # The pytest code
    from {import_name} import ...
    def test_feature():
        assert ...
    ```
    """

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_request},
    ]

    max_retries = 3
    for attempt in range(max_retries):
        print(f"\n🔄 Attempt {attempt + 1}/{max_retries}...")

        completion = client.chat.completions.create(
            model="llama3",
            messages=messages,  # type: ignore[arg-type]
        )
        response_text = completion.choices[0].message.content
        if not response_text:
            continue

        result = parse_llm_response(response_text)
        print(f"🧠 Plan: {result['thought_process']}")

        if not result["new_code"]:
            print("⛔ Error: No code block found. Retrying...")
            continue

        proposed_content = str(result["new_code"])

        # --- FIX 2: Save BEFORE Testing ---
        # We must save the file so pytest can actually import it!
        with open(target_file, "w") as f:
            f.write(proposed_content)
        # ----------------------------------

        # Validate Syntax
        is_valid, error_msg = validate_python_code(proposed_content)
        if not is_valid:
            print(f"\n⛔ Syntax Error:\n{error_msg}")
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": f"Syntax Error: {error_msg}\nFix the code."})
            continue

        # Run Tests
        if result["test_code"]:
            print("🧪 Running Unit Tests...")
            test_filename = "sandbox/test_temp.py"
            with open(test_filename, "w") as f:
                f.write(str(result["test_code"]))

            tests_passed, test_output = run_pytest(test_filename)
            if not tests_passed:
                print(f"❌ Tests Failed:\n{test_output}")
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "user", "content": f"Tests Failed:\n{test_output}\nFix the code."})
                continue
            else:
                print("✅ Tests Passed!")

        # Success! Show Diff
        show_diff(current_content, proposed_content)

        if input("\n❓ Apply this change? (y/n): ").lower() == "y":
            print(f"💾 Saved to {target_file}")
            return
        else:
            print("❌ Change rejected. Reverting file...")
            # --- FIX 3: Revert on Rejection ---
            with open(target_file, "w") as f:
                f.write(current_content)
            return

    # If all retries fail, revert to original
    print("\n❌ Failed to generate valid code. Reverting...")
    with open(target_file, "w") as f:
        f.write(current_content)


# --- MAIN ENTRY POINT ---


def main() -> None:
    if len(sys.argv) > 1:
        user_request = sys.argv[1]
    else:
        user_request = input("What feature do you want to add? ")

    # 1. Route
    target_file = select_target_file(user_request)

    # 2. Act
    apply_changes(target_file, user_request)


if __name__ == "__main__":
    main()
