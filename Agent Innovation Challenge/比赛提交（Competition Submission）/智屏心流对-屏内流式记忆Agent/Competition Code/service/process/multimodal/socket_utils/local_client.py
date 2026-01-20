import socket
import threading
import time

import cv2

SERVER_HOST = '10.50.91.127'  # 服务器IP
SERVER_PORT = 5000
# SERVER_HOST = '10.67.53.141'  # 服务器IP
# SERVER_PORT = 5001
VIDEO_FILE = r"C:\Users\a00575982\Desktop\202503音视频流\code\StreamingQA3\data\演示case\芒果.mp4"  # 修改为你的本地视频文件路径

# 全局变量控制线程退出
thread_exit = False
thread_lock = threading.Lock()


class VideoForwarder(threading.Thread):
    def __init__(self):
        super(VideoForwarder, self).__init__()
        self.frame = None  # 存储当前视频帧
        self.client = None  # 服务器socket连接
        self.count = 0

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
        # ------debug------
        # if self.count % 100 == 0:
        #     save_bytes_to_file(frame_data, rf"./client_image_{self.count}.jpg")
        frame_len = len(frame_data)

        try:
            # 先发送帧长度信息，再发送帧数据
            self.client.sendall(frame_len.to_bytes(4, byteorder='big'))
            self.client.sendall(frame_data)
            self.count += 1
        except Exception as e:
            print(f"转发错误: {e}")
            global thread_exit
            thread_exit = True


def ipcam():
    """主函数：接收本地视频并管理转发线程"""
    global thread_exit
    # 开启本地视频文件
    capture = cv2.VideoCapture(VIDEO_FILE)
    if not capture.isOpened():
        print(f"无法打开视频文件: {VIDEO_FILE}")
        return

    cv2.namedWindow("Local Video Stream", cv2.WINDOW_NORMAL)

    # 启动转发线程
    forward_thread = VideoForwarder()
    forward_thread.daemon = True  # 主线程退出时自动终止
    forward_thread.start()

    num = 0  # 截图计数器
    try:
        while not thread_exit:
            # 帧的形状为(height, width, channels)=(528, 1168, 3)，表示一个3通道图像，
            # 但OpenCV通道顺序是 BGR。
            success, frame = capture.read()
            if not success:
                print("视频流读取失败或视频结束")
                break

            # 显示摄像头画面
            cv2.imshow("Local Video Stream", frame)

            # 更新转发线程的当前帧（线程安全）
            thread_lock.acquire()
            forward_thread.frame = frame.copy()  # 使用深拷贝避免竞争
            thread_lock.release()

            # 按键处理
            key = cv2.waitKey(10)  # 可根据视频帧率调整等待时间
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
    while True:
        try:
            ipcam()
            # 如果 ipcam() 正常退出，break 退出循环
            break
        except Exception as e:
            print(f"[Error] {e}. Restarting ipcam in 5 seconds...")
            time.sleep(5)
