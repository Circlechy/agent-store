import os
import shutil


def delete_directory(path):
    if os.path.exists(path):
        shutil.rmtree(path)
        print(f"目录 '{path}' 已删除")
    else:
        print(f"目录 '{path}' 不存在")