from doc_process.utils import logging

logger = logging.get_logger()


class BoundedFIFOQueue:
    """
    固定长度的 FIFO 队列，支持多进程访问和 pickle 序列化。
    """

    def __init__(self, maxsize, manager_list, manager_lock):
        """
        初始化队列。

        :param maxsize: int, 队列最大长度；
        :param manager_list: multiprocessing.Manager().list(), 共享列表；
        :param manager_lock: multiprocessing.Manager().Lock(), 共享锁；
        """
        self.maxsize = maxsize
        self.queue = manager_list
        self.lock = manager_lock

    def __iter__(self):
        with self.lock:
            return iter(list(self.queue))

    def append(self, item):
        """
        向队列中放入一个元素。若队列满，则替换最早的一个元素。
        """
        with self.lock:
            if len(self.queue) >= self.maxsize:
                self.queue.pop(0)
            self.queue.append(item)

    def get(self):
        """
        从队列头部取出一个元素。若队列为空，返回 None。
        """
        with self.lock:
            if not self.queue:
                return None
            return self.queue.pop(0)

    def to_array(self):
        """
        复制队列中的所有元素到一个新数组中，并保持队列不变。

        :return: list, 队列中元素的副本（普通 Python 列表）。
        """
        with self.lock:
            return list(self.queue)

    def qsize(self):
        """
        获取当前队列长度。
        """
        with self.lock:
            return len(self.queue)

    def empty(self):
        """
        检查队列是否为空。
        """
        return self.qsize() == 0

    def full(self):
        """
        检查队列是否已满。
        """
        return self.qsize() == self.maxsize

    def get_segment(self, frame_base64, MAX_RETRIEVAL=3):
        # 查找目标帧并获取前后帧
        result_segment = []
        try:
            with self.lock:
                # 如果缓冲区非空
                if len(self.queue):
                    # 查找目标帧位置（从后向前查找更快）
                    target_idx = -1
                    for i in range(len(self.queue) - 1, -1, -1):
                        if self.queue[i].frame_base64 == frame_base64:
                            target_idx = i
                            break

                    if target_idx >= 0:
                        # 计算前后帧范围
                        start_idx = max(0, target_idx - MAX_RETRIEVAL)
                        end_idx = min(len(self.queue), target_idx + 1)

                        # 提取帧片段
                        result_segment = list(self.queue)[start_idx:end_idx]
        except Exception as e:
            logger.error(e)

        return result_segment

import threading

class ThreadSafeCounter:
    def __init__(self):
        self.value = 0
        self.lock = threading.Lock()

    def increment(self):
        """线程安全地增加计数器"""
        with self.lock:
            self.value += 1

    def get_value(self):
        """线程安全地获取当前计数器值"""
        with self.lock:
            return self.value