import glob
import os
import sys
import time
from typing import Any, Literal, List, Optional

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

# Import tools
from tools import (
    parse_llm_response,
    read_file,
    run_pytest,
    show_diff,
    validate_python_code,
    WorktreeManager,
    ParallelValidator
)

load_dotenv()

# Configuration
API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_ID = "gemini-2.0-flash"

def get_client() -> genai.Client:
    return genai.Client(api_key=API_KEY)

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
    
    INSTRUCTIONS:
    1. Select an existing file if possible.
    2. If the request requires a new file, provide a suitable name.
    3. ⚠️ IMPORTANT: All new files MUST be created inside the 'sandbox/' directory (e.g., 'sandbox/processor.py').
    """

    print("🤔 Routing request to correct file...")
    try:
        client = get_client()
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[system_prompt, user_request],
            config={
                'response_mime_type': 'application/json',
                'response_schema': FileSelection,
            }
        )
        result = response.parsed
        if result:
            print(f"📂 Selected File: {result.file_name} ({result.thought_process})")
            return result.file_name
        return "sandbox/error.py"
    except Exception as e:
        print(f"Routing Error: {e}")
        return "sandbox/error.py"

# --- STEP 2: SURGEON (With Worktree & Parallel Validation) ---

def validate_candidate(wt_path: str, target_file: str, code: str, test_code: Optional[str]) -> dict:
    """Validates a code candidate in its own worktree."""
    rel_target_file = os.path.relpath(target_file, wt_path) if os.path.isabs(target_file) else target_file
    full_target_path = os.path.join(wt_path, rel_target_file)
    
    # Ensure directory exists in worktree
    os.makedirs(os.path.dirname(full_target_path), exist_ok=True)
    
    # Save code
    with open(full_target_path, "w") as f:
        f.write(code)
        
    # Syntax check
    is_valid, error_msg = validate_python_code(code)
    if not is_valid:
        return {"status": "syntax_error", "message": error_msg}
        
    # Run tests
    if test_code:
        test_filename = os.path.join(wt_path, "sandbox/test_candidate.py")
        os.makedirs(os.path.dirname(test_filename), exist_ok=True)
        with open(test_filename, "w") as f:
            f.write(test_code)
            
        tests_passed, test_output = run_pytest("sandbox/test_candidate.py", workdir=wt_path)
        if not tests_passed:
            return {"status": "test_failure", "message": test_output}
            
    return {"status": "success", "code": code}

def apply_changes(target_file: str, user_request: str) -> None:
    # Force sandbox path
    if not target_file.startswith("sandbox/"):
        target_file = os.path.join("sandbox", target_file)

    current_content = read_file(target_file)
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

    print(f"🚀 Initializing isolated worktrees for {target_file}...")
    wt_manager = WorktreeManager(".")
    
    try:
        max_attempts = 2
        candidates = []
        
        # Generate multiple candidates in parallel (simulated by sequential generation here for reliability)
        client = get_client()
        for i in range(max_attempts):
            print(f"🧠 Generating candidate {i+1}...")
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=[system_prompt, user_request],
            )
            response_text = response.text
            if not response_text: continue
            
            result = parse_llm_response(response_text)
            if result["new_code"]:
                candidates.append(result)

        if not candidates:
            print("❌ No valid code candidates generated.")
            return

        # Parallel Validation
        print(f"🧪 Validating {len(candidates)} candidates in parallel worktrees...")
        validator = ParallelValidator(max_workers=len(candidates))
        validation_tasks = []
        wt_paths = []
        
        for i, cand in enumerate(candidates):
            wt_path = wt_manager.create_worktree(f"val-{i}")
            wt_paths.append(wt_path)
            validation_tasks.append((validate_candidate, (wt_path, target_file, cand["new_code"], cand["test_code"])))
            
        results = validator.run_validations(validation_tasks)
        
        # Find first successful result
        successful_cand = None
        for res in results:
            if res["status"] == "success":
                successful_cand = res
                break
        
        if successful_cand:
            print("✅ Found a successful candidate!")
            proposed_content = successful_cand["code"]
            show_diff(current_content, proposed_content)
            
            if input("\n❓ Apply this change to main repository? (y/n): ").lower() == 'y':
                with open(target_file, "w") as f:
                    f.write(proposed_content)
                print(f"💾 Saved to {target_file}")
            else:
                print("❌ Change rejected.")
        else:
            print("❌ All candidates failed validation.")
            for i, res in enumerate(results):
                print(f"Candidate {i+1} failure: {res['status']} - {res.get('message', '')[:100]}...")

    finally:
        print("🧹 Cleaning up worktrees...")
        wt_manager.cleanup_all()

# --- MAIN ENTRY POINT ---

def main() -> None:
    if len(sys.argv) > 1:
        user_request = " ".join(sys.argv[1:])
    else:
        user_request = input("What feature do you want to add? ")

    target_file = select_target_file(user_request)
    apply_changes(target_file, user_request)

if __name__ == "__main__":
    main()
