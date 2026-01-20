"""使用 OldUserManager 的模块"""

from user_manager import OldUserManager


class UserController:
    """用户控制器"""

    def __init__(self):
        self.manager = OldUserManager()

    def create_user(self, name, email):
        """创建用户"""
        user_id = len(self.manager.list_users()) + 1
        return self.manager.add_user(user_id, name, email)

    def get_user_by_id(self, user_id):
        """根据 ID 获取用户"""
        return self.manager.get_user(user_id)


def get_default_manager():
    """获取默认管理器"""
    return OldUserManager()
