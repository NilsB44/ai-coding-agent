import os
import sys
import glob 
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional, Literal
from dotenv import load_dotenv

# Import tools
from tools import read_file, validate_python_code, show_diff, get_file_tree, run_pytest, parse_llm_response

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
    search_text: Optional[str] = Field(description="Code to replace (for 'replace' action).")
    new_code: str = Field(description="The new code.")
    test_code: Optional[str] = Field(description="A corresponding pytest unit test to verify this code works. (Optional)")

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
    
    If the request requires a new file, provide a suitable name (e.g., 'sandbox/new_feature.py').
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
        print(f"📂 Selected File: {result.file_name} ({result.thought_process})")
        return result.file_name
    except Exception as e:
        print(f"Routing Error: {e}")
        return "sandbox/error.py"

# --- STEP 2: SURGEON ---

def apply_changes(target_file: str, user_request: str):
    print(f"🤖 Agent starting on: {target_file}")
    
    # Handle New Files
    if not os.path.exists(target_file):
        print(f"✨ Creating new file: {target_file}")
        with open(target_file, 'w') as f: f.write("")
        current_content = ""
    else:
        current_content = read_file(target_file)

    import_name = target_file.replace("/", ".").replace(".py", "")
    
    system_prompt = f"""
    You are a Python Coding Agent.
    
    CONTEXT:
    File: {target_file}
    Content:
    {current_content}
    
    INSTRUCTIONS:
    1. You are editing an EXISTING file. 
    2. Your response must contain the **FULL** file content.
    3. **DO NOT** remove existing functions (`add`, `divide`, etc.) unless explicitly asked.
    4. **INCLUDE** the existing code in your output, then add the new code.
    5. Write a pytest unit test.
    
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
    from {import_name} import ...  <-- USE THIS EXACT IMPORT
    def test_feature():
        assert ...
    ```
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_request}
    ]

    max_retries = 3
    for attempt in range(max_retries):
        print(f"\n🔄 Attempt {attempt + 1}/{max_retries}...")
        
        # 1. Call LLM (No Pydantic, just string)
        completion = client.chat.completions.create(
            model="llama3",
            messages=messages,
        )
        response_text = completion.choices[0].message.content
        
        # 2. Parse manually
        result = parse_llm_response(response_text)
        print(f"🧠 Plan: {result['thought_process']}")
        
        # 3. Sanity Check
        if not result['new_code']:
            print("⛔ Error: No code block found. Retrying...")
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": "You forgot the ```python``` block! Please write the code."})
            continue

        # 4. Save & Test (Default to Overwrite for stability)
        proposed_content = result['new_code']
        
        # Validate
        is_valid, error_msg = validate_python_code(proposed_content)
        if not is_valid:
            print(f"\n⛔ Syntax Error:\n{error_msg}")
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": f"Syntax Error: {error_msg}\nFix the code block."})
            continue

        # Run Tests
        if result['test_code']:
            print("🧪 Running Unit Tests...")
            test_filename = "sandbox/test_temp.py"
            with open(test_filename, "w") as f:
                f.write(result['test_code'])
            
            tests_passed, test_output = run_pytest(test_filename)
            if not tests_passed:
                print(f"❌ Tests Failed:\n{test_output}")
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "user", "content": f"Tests Failed:\n{test_output}\nFix the code."})
                continue
            else:
                print("✅ Tests Passed!")

        # Success!
        show_diff(current_content, proposed_content)
        if input("\n❓ Apply this change? (y/n): ").lower() == 'y':
            with open(target_file, "w") as f:
                f.write(proposed_content)
            print(f"💾 Saved to {target_file}")
            return

    print("\n❌ Failed to generate valid code.")

# --- MAIN ENTRY POINT ---

def main():
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