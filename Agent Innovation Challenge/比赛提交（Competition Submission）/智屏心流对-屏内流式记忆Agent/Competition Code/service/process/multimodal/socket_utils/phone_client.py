import cv2
import socket
import numpy as np
import threading

# SERVER_HOST = '10.50.91.127'  # 设备C的局域网IP
SERVER_HOST = '10.67.53.57'
SERVER_PORT = 5000
PHONE_HOST = '192.168.137.160'

# 全局变量控制线程退出
thread_exit = False
thread_lock = threading.Lock()


class VideoForwarder(threading.Thread):

    def __init__(self):
        super(VideoForwarder, self).__init__()
        self.frame = None  # 存储当前视频帧
        self.client = None  # 服务器socket连接

    def run(self):
        global thread_exit
        # 连接服务器的TCP服务
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect((SERVER_HOST, SERVER_PORT))
        print(f"已连接到服务器: {SERVER_HOST}:{SERVER_PORT}")

        while not thread_exit:
            if self.frame is not None:
                # 转发当前帧到服务器
                self.forward_frame(self.frame)

    def forward_frame(self, frame):
        # JPEG压缩传输（平衡质量和延迟）
        _, img_encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        frame_data = img_encoded.tobytes()
        frame_len = len(frame_data)

        try:
            # 先发送帧长度信息，再发送帧数据
            self.client.sendall(frame_len.to_bytes(4, byteorder='big'))
            self.client.sendall(frame_data)
        except Exception as e:
            print(f"转发错误: {e}")
            global thread_exit
            thread_exit = True


def ipcam():
    """主函数：接收手机视频并管理转发线程[1,8](@ref)"""
    global thread_exit
    # 开启ip摄像头（手机）
    video_url = f"http://admin:admin@{PHONE_HOST}:8081/"
    capture = cv2.VideoCapture(video_url)
    if not capture.isOpened():
        print("无法连接到手机的摄像头")
        return

    cv2.namedWindow("Device A - Live Stream", cv2.WINDOW_NORMAL)

    # 启动转发线程
    forward_thread = VideoForwarder()
    forward_thread.daemon = True  # 主线程退出时自动终止
    forward_thread.start()

    num = 0  # 截图计数器
    try:
        while not thread_exit:
            success, frame = capture.read()
            if not success:
                print("视频流读取失败")
                break

            # 显示摄像头画面
            cv2.imshow("Device A - Live Stream", frame)

            # 更新转发线程的当前帧（线程安全）
            thread_lock.acquire()
            forward_thread.frame = frame.copy()  # 使用深拷贝避免竞争
            thread_lock.release()

            # 按键处理
            key = cv2.waitKey(10)
            if key == 27:  # ESC退出
                print("程序终止...")
                break
            if key == ord(' '):  # 空格键截图
                num += 1
                filename = f"frames_{num}.jpg"
                cv2.imwrite(filename, frame)
                print(f"截图已保存: {filename}")

    finally:
        # 资源清理
        thread_exit = True
        capture.release()
        cv2.destroyAllWindows()
        if forward_thread.client:
            forward_thread.client.close()
        forward_thread.join(timeout=1.0)
        print("资源已释放")


if __name__ == '__main__':
    ipcam()