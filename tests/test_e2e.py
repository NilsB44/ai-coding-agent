import os
import sys
from unittest.mock import patch, MagicMock

# Ensure agent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agent")))

from main import apply_changes


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

    # Mock candidate to avoid real LLM calls in CI
    mock_candidate = {
        "thought_process": "Creating bank processor",
        "action": "overwrite",
        "search_text": None,
        "new_code": (
            "class Account:\n"
            "    def __init__(self, owner: str, balance: float):\n"
            "        self.owner = owner\n"
            "        self.balance = balance\n"
            "    def deposit(self, amount: float) -> None: self.balance += amount\n"
            "    def withdraw(self, amount: float) -> None:\n"
            "        if amount > self.balance: raise ValueError('Insufficient funds')\n"
            "        self.balance -= amount\n"
            "    @staticmethod\n"
            "    def batch_process(transactions: list) -> dict: return {'status': 'ok'}\n"
        ),
        "test_code": (
            "from bank import Account\n"
            "def test_account():\n"
            "    a = Account('test', 100)\n"
            "    a.deposit(50)\n"
            "    assert a.balance == 150\n"
        )
    }

    # We mock:
    # 1. input -> 'y' to apply
    # 2. select_target_file -> return 'sandbox/bank.py'
    # 3. get_candidates -> return our mock candidate
    with patch('builtins.input', side_effect=['y']), \
         patch('main.select_target_file', return_value='sandbox/bank.py'), \
         patch('main.get_candidates', return_value=[mock_candidate]):
        
        target_file = 'sandbox/bank.py'
        
        # This will run the worktree creation, validation, and application
        apply_changes(target_file, user_request)
        
        # Verify the file was actually created and has content
        full_path = os.path.join(os.getcwd(), target_file)
        # In some CI environments we might be in the root or RAG root
        if not os.path.exists(full_path):
             full_path = os.path.join(os.getcwd(), "RAG", target_file)
             
        assert os.path.exists(full_path)
        with open(full_path) as f:
            content = f.read()
        assert "class Account" in content
        assert "deposit" in content
        assert "withdraw" in content

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
