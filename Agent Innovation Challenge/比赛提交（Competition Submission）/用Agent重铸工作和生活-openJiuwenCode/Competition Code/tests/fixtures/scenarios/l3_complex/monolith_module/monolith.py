"""大型单体模块 - 需要拆分"""

import json
import os
import hashlib
from datetime import datetime


# ============ 用户相关功能 ============

class User:
    def __init__(self, user_id, name, email):
        self.user_id = user_id
        self.name = name
        self.email = email
        self.created_at = datetime.now()

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'name': self.name,
            'email': self.email,
            'created_at': self.created_at.isoformat()
        }


def create_user(user_id, name, email):
    return User(user_id, name, email)


def validate_email(email):
    return '@' in email and '.' in email


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ============ 订单相关功能 ============

class Order:
    def __init__(self, order_id, user_id, items):
        self.order_id = order_id
        self.user_id = user_id
        self.items = items
        self.status = 'pending'
        self.created_at = datetime.now()

    def calculate_total(self):
        return sum(item['price'] * item['quantity'] for item in self.items)

    def to_dict(self):
        return {
            'order_id': self.order_id,
            'user_id': self.user_id,
            'items': self.items,
            'status': self.status,
            'total': self.calculate_total()
        }


def create_order(order_id, user_id, items):
    return Order(order_id, user_id, items)


def validate_order_items(items):
    for item in items:
        if item.get('price', 0) <= 0:
            return False
        if item.get('quantity', 0) <= 0:
            return False
    return True


# ============ 支付相关功能 ============

class Payment:
    def __init__(self, payment_id, order_id, amount, method):
        self.payment_id = payment_id
        self.order_id = order_id
        self.amount = amount
        self.method = method
        self.status = 'pending'

    def process(self):
        # 模拟支付处理
        self.status = 'completed'
        return True

    def to_dict(self):
        return {
            'payment_id': self.payment_id,
            'order_id': self.order_id,
            'amount': self.amount,
            'method': self.method,
            'status': self.status
        }


def create_payment(payment_id, order_id, amount, method):
    return Payment(payment_id, order_id, amount, method)


def validate_payment_method(method):
    valid_methods = ['credit_card', 'debit_card', 'paypal', 'bank_transfer']
    return method in valid_methods


# ============ 工具函数 ============

def generate_id():
    import uuid
    return str(uuid.uuid4())[:8]


def format_currency(amount):
    return f"${amount:.2f}"


def save_to_file(data, filepath):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def load_from_file(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return None
