"""OldUserManager 的测试"""

import pytest
from user_manager import OldUserManager


class TestOldUserManager:
    """测试 OldUserManager"""

    def test_add_user(self):
        manager = OldUserManager()
        user = manager.add_user(1, "Alice", "alice@example.com")
        assert user['name'] == "Alice"

    def test_get_user(self):
        manager = OldUserManager()
        manager.add_user(1, "Bob", "bob@example.com")
        user = manager.get_user(1)
        assert user['email'] == "bob@example.com"

    def test_list_users(self):
        manager = OldUserManager()
        manager.add_user(1, "User1", "user1@example.com")
        manager.add_user(2, "User2", "user2@example.com")
        users = manager.list_users()
        assert len(users) == 2
