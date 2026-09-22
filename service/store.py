from typing import Dict, Optional
from .models import Order


orders: Dict[str, Order] = {}


def save_order(order: Order) -> None:
    orders[order.order_id] = order


def get_order(order_id: str) -> Optional[Order]:
    return orders.get(order_id)


def get_all_orders() -> list[Order]:
    return list(orders.values())


def delete_order(order_id: str) -> None:
    orders.pop(order_id, None)