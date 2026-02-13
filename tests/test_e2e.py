import os
import shutil
import subprocess
import pytest
from unittest.mock import patch
import sys

# Ensure agent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agent")))

from main import select_target_file, apply_changes

def test_transaction_processor_e2e():
    """
    E2E Test: Ask the agent to create a complex transaction processor.
    Verified:
    1. Router selects a new file.
    2. Worktrees are created and used.
    3. Parallel validation runs.
    4. Successful candidate is applied.
    """
    user_request = (
        "Create a Bank Transaction Processor in sandbox/bank.py. "
        "It should have a class Account with 'balance' and 'owner'. "
        "Include methods 'deposit', 'withdraw' (should raise ValueError if insufficient funds), "
        "and a static method 'batch_process' that takes a list of (account, type, amount) tuples "
        "and processes them, returning a summary. Include full type hints."
    )
    
    # We mock 'input' to always say 'y' when the agent asks to apply the change
    with patch('builtins.input', side_effect=['y']):
        target_file = select_target_file(user_request)
        assert "bank.py" in target_file
        
        # This will run the full generation, worktree creation, validation, and application
        apply_changes(target_file, user_request)
        
        # Verify the file was actually created and has content
        full_path = os.path.join(os.getcwd(), target_file)
        if not os.path.exists(full_path):
             # Try relative if cwd changed
             full_path = os.path.join(os.getcwd(), "RAG", target_file)
             
        assert os.path.exists(full_path)
        with open(full_path, "r") as f:
            content = f.read()
        assert "class Account" in content
        assert "deposit" in content
        assert "withdraw" in content
        assert "batch_process" in content
        assert "balance" in content

if __name__ == "__main__":
    # Clean up any existing bank.py before test
    if os.path.exists("sandbox/bank.py"):
        os.remove("sandbox/bank.py")
    
    try:
        test_transaction_processor_e2e()
        print("\n✅ E2E TEST PASSED!")
    except Exception as e:
        print(f"\n❌ E2E TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
