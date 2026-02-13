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
    def batch_process(transactions: list[tuple["Account", str, float]]) -> dict[str, Any]:
        summary: dict[str, int | list[str]] = {"successful": 0, "failed": 0, "errors": []}
        for account, action, amount in transactions:
            try:
                if action == "deposit":
                    account.deposit(amount)
                elif action == "withdraw":
                    account.withdraw(amount)
                else:
                    raise ValueError(f"Unknown action: {action}")

                success_count = summary["successful"]
                if isinstance(success_count, int):
                    summary["successful"] = success_count + 1
            except Exception as e:
                failed_count = summary["failed"]
                if isinstance(failed_count, int):
                    summary["failed"] = failed_count + 1

                errors_list = summary["errors"]
                if isinstance(errors_list, list):
                    errors_list.append(str(e))
        return summary
