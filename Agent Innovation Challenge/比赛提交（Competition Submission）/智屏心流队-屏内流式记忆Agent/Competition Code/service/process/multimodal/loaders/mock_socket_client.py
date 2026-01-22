import socket
import cv2
import time

SERVER_IP = '10.50.91.127'  # 服务端IP
SERVER_PORT = 5000       # 服务端端口
VIDEO_PATH = '/data01/atd/code/StreamingQA2/data/car/video/test1.mp4'  # 本地视频文件路径

def send_video():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((SERVER_IP, SERVER_PORT))

    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print("无法打开视频文件")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            break  # 视频结束
        # 编码为jpg格式
        _, img_encoded = cv2.imencode('.jpg', frame)
        data = img_encoded.tobytes()
        # 发送4字节长度
        client.send(len(data).to_bytes(4, byteorder='big'))
        # 发送帧数据
        client.sendall(data)
        time.sleep(1/25)  # 控制帧率，假设25fps

    cap.release()
    client.close()
    print("视频发送完毕")

if __name__ == '__main__':
    send_video()