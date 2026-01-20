import socket
import cv2
import numpy as np
import threading
import queue
import time

# 配置参数
RECEIVE_PORT = 5001  # 中转器监听客户端的端口
FORWARD_HOST = '127.0.0.1'  # 目标服务器地址（转发目标）
FORWARD_PORT = 5000  # 转发目标端口
MAX_QUEUE_SIZE = 100  # 帧队列最大缓存数量

# 全局变量
frame_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)  # 线程安全队列
stop_event = threading.Event()  # 控制线程退出


class FrameReceiver(threading.Thread):
    """接收视频帧的线程"""

    def __init__(self, client_socket):
        super().__init__()
        self.client_socket = client_socket
        self.daemon = True

    def run(self):
        buffer = b''  # 存储未处理的数据
        try:
            while not stop_event.is_set():
                # 接收帧长度信息（4字节）
                while len(buffer) < 4:
                    data = self.client_socket.recv(4 - len(buffer))
                    if not data:
                        print("客户端连接断开")
                        stop_event.set()
                        return
                    buffer += data

                frame_len = int.from_bytes(buffer[:4], byteorder='big')
                buffer = buffer[4:]

                # 接收完整帧数据
                while len(buffer) < frame_len:
                    data = self.client_socket.recv(frame_len - len(buffer))
                    if not data:
                        print("接收数据中断")
                        stop_event.set()
                        return
                    buffer += data

                # 解码帧数据
                frame_data = buffer[:frame_len]
                buffer = buffer[frame_len:]

                # 将帧放入队列
                try:
                    frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if frame is not None:
                        frame_queue.put(frame, block=False)
                except queue.Full:
                    print("帧队列已满，丢弃一帧")

        except Exception as e:
            print(f"接收线程异常: {e}")
            stop_event.set()


class FrameForwarder(threading.Thread):
    """转发视频帧的线程"""

    def __init__(self):
        super().__init__()
        self.daemon = True
        self.forward_socket = None

    def run(self):
        try:
            # 连接到转发目标服务器
            self.forward_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.forward_socket.connect((FORWARD_HOST, FORWARD_PORT))
            print(f"已连接到转发服务器: {FORWARD_HOST}:{FORWARD_PORT}")

            while not stop_event.is_set():
                try:
                    frame = frame_queue.get(timeout=0.1)  # 非阻塞获取
                    # 重新编码为JPEG
                    _, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    frame_data = encoded.tobytes()
                    frame_len = len(frame_data)

                    # 发送帧长度和帧数据
                    self.forward_socket.sendall(frame_len.to_bytes(4, byteorder='big'))
                    self.forward_socket.sendall(frame_data)

                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"转发错误: {e}")
                    stop_event.set()

        except Exception as e:
            print(f"连接转发服务器失败: {e}")
            stop_event.set()
        finally:
            if self.forward_socket:
                self.forward_socket.close()


class FrameDisplayer(threading.Thread):
    """视频显示线程"""

    def __init__(self):
        super().__init__()
        self.daemon = True

    def run(self):
        cv2.namedWindow("Video Stream", cv2.WINDOW_NORMAL)
        while not stop_event.is_set():
            try:
                frame = frame_queue.get(timeout=0.1)
                cv2.imshow("Video Stream", frame)
                # 按ESC退出
                if cv2.waitKey(1) == 27:
                    stop_event.set()
            except queue.Empty:
                continue
        cv2.destroyAllWindows()


def start_server():
    """启动TCP服务器"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', RECEIVE_PORT))
    server_socket.listen(1)
    print(f"中转器正在监听端口 {RECEIVE_PORT}...")

    try:
        while not stop_event.is_set():
            client_socket, addr = server_socket.accept()
            print(f"客户端已连接: {addr}")

            # 启动接收线程
            receiver = FrameReceiver(client_socket)
            receiver.start()

            # 启动转发线程
            forwarder = FrameForwarder()
            forwarder.start()

            # 启动显示线程
            displayer = FrameDisplayer()
            displayer.start()

            # 等待线程完成
            receiver.join()
            forwarder.join()
            displayer.join()

            print("客户端连接已关闭，等待新连接...")

    except KeyboardInterrupt:
        print("收到中断信号，正在关闭...")
    finally:
        server_socket.close()
        stop_event.set()


if __name__ == '__main__':
    start_server()