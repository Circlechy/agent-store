import argparse
import json
import os

import time
import traceback
from collections import deque

import torch
from torch.multiprocessing import Queue, Process
import torch.multiprocessing as mp
from doc_process.config_repository.config import Config
from doc_process.utils import logging
from service.process.common.client.es_client import ESClient
from service.process.common.client.es_request import delete_all_documents_in_index
from service.process.multimodal.loaders.image_loader import ImageLoader
from service.process.multimodal.loaders.socket_server import socket_server
from service.process.multimodal.loaders.stream_loader_buffer import StreamLoaderBuffer
from service.process.multimodal.loaders.video_loader_buffer import VideoLoaderBuffer
from service.process.multimodal.multiprocess_utils import BoundedFIFOQueue
from service.process.multimodal.parse_config import ParseConfig
from service.process.multimodal.vstream.utils import disable_torch_init
from service.process.multimodal.qwen_process_service import QwenProcessService
from service.search.vstream.qwen_search_service import QwenSearchService


current_dir = os.path.dirname(os.path.abspath(__file__))
logger = logging.get_logger()


#但请确保所有多进程相关的代码都在__main__下，包括 Queue 的创建。 !!!!
if __name__ == "__main__":

    try:
        # 配置代理信息
        # os.environ["http_proxy"] = "http://10.155.97.225:3128"
        # os.environ["https_proxy"] = os.environ["http_proxy"]
        # os.environ["no_proxy"] = "localhost,127.0.0.1"

        os.environ["CUDA_VISIBLE_DEVICES"] = "0"

        # 清空ES短期记忆信息：
        host = "https://10.168.12.121:9200"
        index_name = "short_term"
        result = delete_all_documents_in_index(
            host_url=host,
            index_name=index_name,
        )
        # 处理结果
        if result is not None:
            print(f"成功删除 {index_name} 索引中的所有文档:")
            print(f"已删除文档数量: {result.get('deleted', 0)}")
        else:
            print(f"未能清空 {index_name} 索引")


        args, input_dict = init_params(ip="127")

        embedding_file = os.path.join(current_dir, "{}-video_embedding.bin".format(int(time.time())))

        # load & process
        yaml_config_path = ParseConfig.parse_config("dev")
        yaml_config = Config(config_file_path=yaml_config_path)
        config_dict = yaml_config.get_final_config()

        process_service = QwenProcessService(config_dict)


        # search
        search_service = QwenSearchService(config_dict, args, embedding_file=embedding_file)

        torch.multiprocessing.set_start_method('spawn', force=True)
        disable_torch_init()



        # # ---------------串行------------------
        # file = "/opt/huawei/data2/atd/code/StreamingQA/data/car/video/test1.mp4"

        # loader = VideoLoader()
        # frame_queue = Queue(maxsize=1000)
        # llm_frame_queue = deque(maxlen=32)
        # produce_all_frames_worker(file, loader, frame_queue, llm_frame_queue, 2, 1)
        # consume_frames_worker(input_dict, process_service, frame_queue)
        # question = "Which parking space is my car parked in?"
        # answer = search_service.get_answer(args, question, llm_frame_queue)
        # logger.info(answer)

        # # ---------------并行------------------
        file = "/tmp/pycharm_project_361/Seeking1.mp4"

        loader = StreamLoaderBuffer()
        video_frame_global = Queue()
        frame_queue = Queue(maxsize=1000)

        # 创建 Manager 实例并初始化共享资源
        manager = mp.Manager()
        shared_list = manager.list()
        shared_lock = manager.Lock()

        # 创建固定长度的 FIFO 队列
        llm_frame_queue = BoundedFIFOQueue(maxsize=32, manager_list=shared_list, manager_lock=shared_lock)


        send = Process(
            target=socket_server,
            args=(video_frame_global,),
            daemon=True
        )
        send.start()

        # produce_all_frames_worker(video_frame_global, loader, frame_queue, 5, 1)

        produce = Process(
            target=produce_all_frames_worker,
            args=(video_frame_global, loader, frame_queue, llm_frame_queue, 5, 1),
            daemon=True
        )
        produce.start()

        consumer_process = Process(target=consume_frames_worker,
                                   args=(input_dict, process_service, frame_queue,),
                                   daemon=True
                                   )
        consumer_process.start()

        question = "我的包在哪里？"
        answer, image_answer = search_service.get_answer(args, question, llm_frame_queue)
        logger.info(answer)

        while True:
            time.sleep(5)
            question = "我的包在哪里？"
            answer, image_answer = search_service.get_answer(args, question, llm_frame_queue)
            logger.info(answer)

    except Exception as e:
        logger.error(traceback.format_exc())
    logger.info("All processes finished.")


