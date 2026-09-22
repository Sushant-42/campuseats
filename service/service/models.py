from dataclasses import dataclass
from typing import List


@dataclass
class OrderItem:
    item_id: str
    quantity: int


@dataclass
class Order:
    order_id: str
    student_id: str
    restaurant_id: str
    items: List[OrderItem]
    status: str = "pending"
    total: float = 0.0