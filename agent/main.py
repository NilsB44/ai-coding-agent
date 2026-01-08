import os
import sys
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional, Literal
from tools import read_file, validate_python_code

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama", 
)

class CodeUpdate(BaseModel):
    thought_process: str = Field(description="Analyze the request and explain what needs to be changed.")
    action: Literal["append", "replace"] = Field(description="Whether to append new code or replace existing code.")

    # "search_text" is only needed for replacement
    search_text: Optional[str] = Field(description="The exact code block to be replaced (required if action is 'replace').")
    
    # "new_code" is the replacement code OR the new code to append
    new_code: str = Field(description="The new code to insert.")


def main():
    target_file = "sandbox/math_lib.py"
    
    # --- NEW: DYNAMIC INPUT ---
    # Check if the user provided an argument (e.g., python main.py "Add fibonacci")
    if len(sys.argv) > 1:
        user_request = sys.argv[1]
    else:
        # If no argument, ask interactively
        user_request = input("What feature do you want to add? ")
        
    if not user_request.strip():
        print("Error: Request cannot be empty.")
        return
    # --------------------------

    print(f"🤖 Agent starting on: {target_file}")
    print(f"📝 Request: {user_request}")

    current_content = read_file(target_file)
    if not current_content and not os.path.exists(target_file):
        current_content = "# Math Library\n"

    # Initialize Chat History

    system_prompt = f"""
    You are an expert Python engineer. 
    Your task is to modify the provided code file based on the user's request.
    
    Current File Content:
    {current_content}
    
    INSTRUCTIONS:
    1. If you are adding new functionality, set action="append".
    2. If you are fixing a bug or updating existing code, set action="replace".
    3. For "replace", `search_text` must match the existing code EXACTLY (whitespace and all).
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_request}
    ]

    # --- THE RETRY LOOP ---
    max_retries = 3
    for attempt in range(max_retries):
        print(f"\n🔄 Attempt {attempt + 1}/{max_retries}...")
        
        # Call LLM
        completion = client.beta.chat.completions.parse(
            model="llama3",
            messages=messages,
            response_format=CodeUpdate,
        )
        
        result = completion.choices[0].message.parsed
        print(f"📝 Generated Code:\n{result.new_code}")

        if result.action == "append":
            proposed_content = current_content + "\n\n" + result.new_code
        
        elif result.action == "replace":
            # Check if we can actually find the text
            if result.search_text not in current_content:
                print(f"⛔ Error: Could not find the code block to replace.\nSearch text was:\n{result.search_text}")
                # Feedback to the LLM
                messages.append({"role": "assistant", "content": result.model_dump_json()})
                messages.append({"role": "user", "content": "I could not find that exact code in the file. Please provide the EXACT `search_text` from the file to replace."})
                continue # Retry
            
            # Perform the replacement
            proposed_content = current_content.replace(result.search_text, result.new_code)

        # Validate (Same as before)
        is_valid, error_msg = validate_python_code(proposed_content)

        if is_valid:
            print("\n✅ Code passed syntax check.")
            with open(target_file, "w") as f:
                f.write(proposed_content)
            print(f"💾 Saved to {target_file}")
            return # Success! Exit the loop.
        else:
            print(f"\n⛔ Syntax Error: {error_msg}")
            print("🔧 Asking agent to fix it...")
            
            # FEEDBACK LOOP: Add the error to the memory
            messages.append({"role": "assistant", "content": result.new_code}) # What it wrote
            messages.append({"role": "user", "content": f"Your code had a syntax error: {error_msg}. Please rewrite it correctly."})
    
    print("\n❌ Failed to generate valid code after 3 attempts.")

if __name__ == "__main__":
    main()
