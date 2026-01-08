import os
import sys
import glob # <--- NEW: To list files
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional, Literal
from dotenv import load_dotenv

# Import tools
from tools import read_file, validate_python_code, show_diff

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
    action: Literal["append", "replace"] = Field(description="Whether to append new code or replace existing code.")
    search_text: Optional[str] = Field(description="The exact code block to be replaced (required if action is 'replace').")
    new_code: str = Field(description="The new code to insert.")

# --- STEP 1: ROUTER ---

def select_target_file(user_request: str) -> str:
    """Decides which file to edit based on the user request."""
    
    # Get list of files in sandbox
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

# --- STEP 2: SURGEON (Your existing logic) ---

def apply_changes(target_file: str, user_request: str):
    print(f"🤖 Agent starting on: {target_file}")
    
    # Handle New Files
    if not os.path.exists(target_file):
        print(f"✨ Creating new file: {target_file}")
        current_content = ""
        # Create empty file so we can read it
        with open(target_file, 'w') as f: f.write("")
    else:
        current_content = read_file(target_file)

    messages = [
        {"role": "system", "content": f"""
        You are an expert Python engineer. 
        Your task is to modify the provided code file based on the user's request.
        
        Current File Content:
        {current_content}
        
        INSTRUCTIONS:
        1. If you are adding new functionality, set action="append".
        2. If you are fixing a bug or updating existing code, set action="replace".
        3. For "replace", `search_text` must match the existing code EXACTLY.
        """},
        {"role": "user", "content": user_request}
    ]

    # Retry Loop
    max_retries = 3
    for attempt in range(max_retries):
        print(f"\n🔄 Attempt {attempt + 1}/{max_retries}...")
        
        completion = client.beta.chat.completions.parse(
            model="llama3",
            messages=messages,
            response_format=CodeUpdate,
        )
        result = completion.choices[0].message.parsed
        print(f"🧠 Plan: {result.thought_process}")

        # Check for lazy empty code
        if not result.new_code.strip() and result.action == "append":
             print("⛔ Error: Empty code generated.")
             continue

        # Logic for Applying Changes
        if result.action == "append":
            proposed_content = current_content + "\n\n" + result.new_code
        elif result.action == "replace":
            if result.search_text not in current_content:
                print(f"⛔ Error: Could not find search text.")
                messages.append({"role": "assistant", "content": result.model_dump_json()})
                messages.append({"role": "user", "content": "I could not find that exact code block. Please provide the EXACT `search_text`."})
                continue
            proposed_content = current_content.replace(result.search_text, result.new_code)

        # Validation
        is_valid, error_msg = validate_python_code(proposed_content)

        if is_valid:
            print("\n✅ Code passed syntax check.")
            show_diff(current_content, proposed_content)
            
            if input("\n❓ Apply this change? (y/n): ").lower() == 'y':
                with open(target_file, "w") as f:
                    f.write(proposed_content)
                print(f"💾 Saved to {target_file}")
                return
            else:
                print("❌ Change rejected.")
                return
        else:
            print(f"\n⛔ Syntax Error: {error_msg}")
            messages.append({"role": "assistant", "content": result.model_dump_json()}) 
            messages.append({"role": "user", "content": f"Syntax Error: {error_msg}. Fix it."})
    
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