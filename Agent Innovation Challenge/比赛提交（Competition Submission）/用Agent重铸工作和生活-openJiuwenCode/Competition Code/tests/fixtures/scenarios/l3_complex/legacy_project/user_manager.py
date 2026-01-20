"""遗留项目 - 需要重构的代码"""

class OldUserManager:
    """旧的用户管理器 - 需要重命名为 UserService"""

    def __init__(self):
        self.users = {}

    def add_user(self, user_id, name, email):
        """添加用户"""
        self.users[user_id] = {
            'id': user_id,
            'name': name,
            'email': email
        }
        return self.users[user_id]

    def get_user(self, user_id):
        """获取用户"""
        return self.users.get(user_id)

    def update_user(self, user_id, **kwargs):
        """更新用户"""
        if user_id in self.users:
            self.users[user_id].update(kwargs)
            return self.users[user_id]
        return None

    def delete_user(self, user_id):
        """删除用户"""
        if user_id in self.users:
            del self.users[user_id]
            return True
        return False

    def list_users(self):
        """列出所有用户"""
        return list(self.users.values())
