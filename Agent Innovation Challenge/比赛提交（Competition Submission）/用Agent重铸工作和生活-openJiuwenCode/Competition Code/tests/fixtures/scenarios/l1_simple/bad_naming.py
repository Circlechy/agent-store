"""命名不规范的代码 - 用于测试变量重命名"""

def calc(x, y, z):
    """计算三个数的加权平均"""
    t = x * 0.5 + y * 0.3 + z * 0.2
    return t


def proc(d):
    """处理数据"""
    r = []
    for i in d:
        if i > 0:
            r.append(i * 2)
    return r


class Mgr:
    """管理器类"""
    def __init__(self):
        self.lst = []

    def add(self, itm):
        self.lst.append(itm)

    def get(self, idx):
        return self.lst[idx] if idx < len(self.lst) else None
