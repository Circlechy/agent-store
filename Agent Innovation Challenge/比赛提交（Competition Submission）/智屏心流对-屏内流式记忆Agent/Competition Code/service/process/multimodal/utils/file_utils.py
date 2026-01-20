import os
import fcntl
import torch
from typing import List, Any


class FileStorageWithLock:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.lock_file = f"{file_path}.lock"

    def _acquire_lock(self):
        """跨平台文件锁"""
        self.fd = open(self.lock_file, 'w')
        fcntl.flock(self.fd, fcntl.LOCK_EX)

    def _release_lock(self):
        """释放锁"""
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        self.fd.close()

    def clear(self):
        """原子化清空文件内容（写入空列表）"""
        self.write([])  # 复用 write 的原子性和锁机制

    def write(self, data: List[Any]):
        temp_path = f"{self.file_path}.tmp"
        try:
            # 写入临时文件
            torch.save(data, temp_path)
            # 加锁替换文件
            self._acquire_lock()
            if os.path.exists(self.file_path):
                os.replace(temp_path, self.file_path)
            else:
                os.rename(temp_path, self.file_path)  # 处理首次写入
        finally:
            if os.path.exists(temp_path):  # 清理残留临时文件
                os.remove(temp_path)
            self._release_lock()

    def read(self) -> List[Any]:
        """读取数据"""
        self._acquire_lock()
        try:
            if not os.path.exists(self.file_path):
                return []
            return torch.load(self.file_path)
        finally:
            self._release_lock()
