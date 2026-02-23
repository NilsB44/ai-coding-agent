import glob
import os
import sys
import logging
from typing import Any, Literal, List, Dict

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

# Import tools
from tools import (
    ParallelValidator,
    WorktreeManager,
    parse_llm_response,
    read_file,
    run_pytest,
    show_diff,
    validate_python_code,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration
API_KEY: str | None = os.environ.get("GEMINI_API_KEY")
MODEL_ID: str = "gemini-2.0-flash"


def get_client() -> genai.Client:
    if not API_KEY:
        logger.error("GEMINI_API_KEY environment variable not set.")
        sys.exit(1)
    return genai.Client(api_key=API_KEY)


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
    files: List[str] = glob.glob("sandbox/*.py")
    file_list_str: str = "\n".join(files)

    system_prompt: str = f"""
    You are a Senior Technical Lead.
    Your job is to select the correct file to edit based on the user's request.
    
    Available Files:
    {file_list_str}
    
    INSTRUCTIONS:
    1. Select an existing file if possible.
    2. If the request requires a new file, provide a suitable name.
    3. ⚠️ IMPORTANT: All new files MUST be created inside the 'sandbox/' directory (e.g., 'sandbox/processor.py').
    """

    logger.info("🤔 Routing request to correct file...")
    try:
        client: genai.Client = get_client()
        response: Any = client.models.generate_content(
            model=MODEL_ID,
            contents=[system_prompt, user_request],
            config={
                "response_mime_type": "application/json",
                "response_schema": FileSelection,
            },
        )
        result: Any = response.parsed
        if isinstance(result, FileSelection):
            logger.info(f"📂 Selected File: {result.file_name} ({result.thought_process})")
            return str(result.file_name)
        return "sandbox/error.py"
    except Exception as e:
        logger.error(f"Routing Error: {e}")
        return "sandbox/error.py"


# --- STEP 2: SURGEON (With Worktree & Parallel Validation) ---


def validate_candidate(wt_path: str, target_file: str, code: str, test_code: str | None) -> Dict[str, Any]:
    """Validates a code candidate in its own worktree."""
    rel_target_file: str = os.path.relpath(target_file, wt_path) if os.path.isabs(target_file) else target_file
    full_target_path: str = os.path.join(wt_path, rel_target_file)

    # Ensure directory exists in worktree
    os.makedirs(os.path.dirname(full_target_path), exist_ok=True)

    # Save code
    try:
        with open(full_target_path, "w") as f:
            f.write(code)
    except Exception as e:
        return {"status": "file_error", "message": str(e)}

    # Syntax check
    is_valid, error_msg = validate_python_code(code)
    if not is_valid:
        return {"status": "syntax_error", "message": error_msg}

    # Run tests
    if test_code:
        test_filename: str = os.path.join(wt_path, "sandbox/test_candidate.py")
        os.makedirs(os.path.dirname(test_filename), exist_ok=True)
        try:
            with open(test_filename, "w") as f:
                f.write(test_code)
        except Exception as e:
            return {"status": "file_error", "message": str(e)}

        tests_passed, test_output = run_pytest("sandbox/test_candidate.py", workdir=wt_path)
        if not tests_passed:
            return {"status": "test_failure", "message": test_output}

    return {"status": "success", "code": code}


def generate_candidates(user_request: str, target_file: str, count: int = 2) -> List[Dict[str, Any]]:
    """Generates multiple code candidates using the LLM."""
    current_content: str = read_file(target_file)
    import_name: str = target_file.replace("/", ".").replace(".py", "")

    system_prompt: str = f"""
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
    candidates: List[Dict[str, Any]] = []
    client: genai.Client = get_client()
    for i in range(count):
        logger.info(f"🧠 Generating candidate {i + 1}...")
        try:
            response: Any = client.models.generate_content(
                model=MODEL_ID,
                contents=[system_prompt, user_request],
            )
            response_text: str | None = response.text
            if not response_text:
                continue

            result: Dict[str, Any] = parse_llm_response(response_text)
            if result.get("new_code"):
                candidates.append(result)
        except Exception as e:
            logger.error(f"Error generating candidate: {e}")

    return candidates


def apply_changes(target_file: str, user_request: str) -> None:
    """Surgeon: Creates worktrees, validates candidates in parallel, and applies the best one."""

    # Force sandbox path
    if not target_file.startswith("sandbox/"):
        target_file = os.path.join("sandbox", target_file)

    current_content: str = read_file(target_file)

    logger.info(f"🚀 Initializing isolated worktrees for {target_file}...")
    wt_manager: WorktreeManager = WorktreeManager(".")

    try:
        candidates: List[Dict[str, Any]] = generate_candidates(user_request, target_file)

        if not candidates:
            logger.error("❌ No valid code candidates generated.")
            return

        # Parallel Validation
        logger.info(f"🧪 Validating {len(candidates)} candidates in parallel worktrees...")
        validator: ParallelValidator = ParallelValidator(max_workers=len(candidates))
        validation_tasks: List[Any] = []
        wt_paths: List[str] = []

        for i, cand in enumerate(candidates):
            wt_path: str = wt_manager.create_worktree(f"val-{i}")
            wt_paths.append(wt_path)
            validation_tasks.append(
                (
                    validate_candidate,
                    (wt_path, target_file, cand["new_code"], cand["test_code"]),
                )
            )

        results: List[Dict[str, Any]] = validator.run_validations(validation_tasks)

        # Find first successful result
        successful_cand: Dict[str, Any] | None = None
        for res in results:
            if res["status"] == "success":
                successful_cand = res
                break

        if successful_cand:
            logger.info("✅ Found a successful candidate!")
            proposed_content: str = successful_cand["code"]
            show_diff(current_content, proposed_content)

            if input("\n❓ Apply this change to main repository? (y/n): ").lower() == "y":
                with open(target_file, "w") as f:
                    f.write(proposed_content)
                logger.info(f"💾 Saved to {target_file}")
            else:
                logger.info("❌ Change rejected.")
        else:
            logger.error("❌ All candidates failed validation.")
            for i, res in enumerate(results):
                logger.error(f"Candidate {i + 1} failure: {res['status']} - {res.get('message', '')[:100]}...")

    finally:
        logger.info("🧹 Cleaning up worktrees...")
        wt_manager.cleanup_all()


# --- MAIN ENTRY POINT ---


def main() -> None:
    user_request: str
    if len(sys.argv) > 1:
        user_request = " ".join(sys.argv[1:])
    else:
        user_request = input("What feature do you want to add? ")

    target_file: str = select_target_file(user_request)
    apply_changes(target_file, user_request)


if __name__ == "__main__":
    main()
