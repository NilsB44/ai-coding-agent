from typing import Any


class Account:
    def __init__(self, owner: str, balance: float = 0.0):
        self.owner = owner
        self.balance = balance

    def deposit(self, amount: float) -> float:
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        self.balance += amount
        return self.balance

    def withdraw(self, amount: float) -> float:
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        if amount > self.balance:
            raise ValueError("Insufficient funds")
        self.balance -= amount
        return self.balance

    @staticmethod
    def batch_process(transactions: list[tuple['Account', str, float]]) -> dict[str, Any]:
        summary = {
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        for account, action, amount in transactions:
            try:
                if action == "deposit":
                    account.deposit(amount)
                elif action == "withdraw":
                    account.withdraw(amount)
                else:
                    raise ValueError(f"Unknown action: {action}")
                summary["successful"] += 1
            except Exception as e:
                summary["failed"] += 1
                summary["errors"].append(str(e))
        return summary
