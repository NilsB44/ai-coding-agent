import os
import sys
from openai import OpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Import your tool
from tools import read_file

# 1. Load Environment Variables (Security Best Practice)
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("Error: OPENAI_API_KEY not found in .env file")
    sys.exit(1)

client = OpenAI(base_url="http://localhost:11434/v1",
	api_key="ollama",
)

# 2. Define the Structure (The Interface)
# This forces the LLM to think before it codes and ensures we get clean code back.
class CodeUpdate(BaseModel):
    thought_process: str = Field(description="Analyze the request and explain what needs to be changed.")
    new_code: str = Field(description="The exact valid Python code to append to the file.")

def main():
    target_file = "sandbox/math_lib.py"
    
    # User Request (In the future, this comes from CLI input)
    user_request = "Add a function that divides two numbers. Handle division by zero safely."

    print(f"🤖 Agent starting on: {target_file}")
    print(f"📝 Request: {user_request}")

    # 3. Read the current state (Context)
    try:
        current_content = read_file(target_file)
    except FileNotFoundError:
        print(f"Error: Could not find {target_file}")
        return

    # 4. The Prompt
    # We explicitly tell the LLM it is a code editor.
    system_prompt = f"""
    You are an expert Python engineer. 
    Your task is to append new functionality to the provided code file based on the user's request.
    
    Current File Content:
    {current_content}
    """

    # 5. Call OpenAI with Structured Output
    completion = client.beta.chat.completions.parse(
        model="llama3",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_request},
        ],
        response_format=CodeUpdate,
    )

    # 6. Parse and Apply
    result = completion.choices[0].message.parsed
    
    print("\n🧠 Agent Reasoning:")
    print(result.thought_process)

    print("\n💻 Appending Code:")
    print(result.new_code)

    # Append to file
    with open(target_file, "a") as f:
        f.write("\n\n" + result.new_code)
    
    print(f"\n✅ Successfully updated {target_file}")

if __name__ == "__main__":
    main()
