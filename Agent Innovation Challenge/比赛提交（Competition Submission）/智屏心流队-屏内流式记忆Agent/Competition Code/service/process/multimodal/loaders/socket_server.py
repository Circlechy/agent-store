import queue
import socket

import cv2
import numpy as np

from doc_process.utils import logging
from service.process.multimodal.utils.image_utils import save_bytes_to_file

logger = logging.get_logger()


def socket_server(video_frame_global):
    HOST = '0.0.0.0'  # 监听所有网络接口
    PORT = 5000

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(1)
    logger.info(f"等待转发设备连接：{HOST}:{PORT}")

    conn, addr = server.accept()
    logger.info(f"转发设备已连接：{addr}")
    count = 0
    while True:
        # 接收帧长度信息
        frame_len = int.from_bytes(conn.recv(4), byteorder='big')
        if not frame_len:
            break

        # 接收帧数据
        frame_data = b''
        while len(frame_data) < frame_len:
            packet = conn.recv(frame_len - len(frame_data))
            if not packet:
                break
            frame_data += packet
        if not frame_data:
            continue

        if video_frame_global.full():
            video_frame_global.get()  # 丢弃最旧帧

        img_array = np.frombuffer(frame_data, dtype=np.uint8)
        # 解码时使用flags=1，表示按原样加载（但OpenCV默认是BGR顺序）
        decoded_img = cv2.imdecode(img_array, flags=1)
        decoded_img = cv2.cvtColor(decoded_img, cv2.COLOR_BGR2RGB)  # BGR -> RGB
        # # ------debug------
        # if count % 100 == 0:
        #     print("")
        #     save_bytes_to_file(frame_data, rf"./server_image_{count}.jpg")
        # 4维度
        decoded_img = np.array([decoded_img])

        video_frame_global.put(decoded_img)

        if count % 300 == 0:
            logger.info(f"socket server send {count}")
        count += 1
        # # 解码并显示
        # frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
        # cv2.imshow("Device C - Live Stream", frame)
        # if cv2.waitKey(1) == 27:  # ESC退出
        #     break
    conn.close()
    server.close()
    cv2.destroyAllWindows()
    logger.info("socket server end.")

def continue_socket_server(video_frame_global):
    while True:
        socket_server(video_frame_global)

if __name__ == "__main__":
    while True:
        socket_server(video_frame_global=queue.Queue())
