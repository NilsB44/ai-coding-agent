import pytest
from bank import Account

def test_account_operations() -> None:
    acc = Account("Nils", 100.0)
    assert acc.deposit(50.0) == 150.0
    assert acc.withdraw(30.0) == 120.0
    with pytest.raises(ValueError, match="Insufficient funds"):
        acc.withdraw(200.0)

def test_batch_process() -> None:
    acc1 = Account("Alice", 100.0)
    acc2 = Account("Bob", 50.0)
    
    transactions = [
        (acc1, "deposit", 50.0),
        (acc2, "withdraw", 20.0),
        (acc1, "withdraw", 300.0), # Should fail
        (acc2, "invalid", 10.0)    # Should fail
    ]
    
    summary = Account.batch_process(transactions)
    assert summary["successful"] == 2
    assert summary["failed"] == 2
    assert len(summary["errors"]) == 2
    assert acc1.balance == 150.0
    assert acc2.balance == 30.0
