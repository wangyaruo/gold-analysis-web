from dataclasses import dataclass


@dataclass(frozen=True)
class PnlResult:
    amount: float
    percent: float


def calculate_pnl(buy_price: float, quantity: float, current_price: float) -> PnlResult:
    if buy_price <= 0:
        raise ValueError("buy_price must be greater than zero")
    if quantity <= 0:
        raise ValueError("quantity must be greater than zero")
    amount = (current_price - buy_price) * quantity
    percent = (amount / (buy_price * quantity)) * 100
    return PnlResult(amount=round(amount, 6), percent=round(percent, 6))
