import argparse
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
import time
import traceback
from collections import deque
import faiss
import json

import torch
import torch.multiprocessing as mp
from torch.multiprocessing import Queue, Process

from doc_process.config_repository.config import Config
from doc_process.utils import logging
from service.process.multimodal.loaders.video_loader_buffer import VideoLoaderBuffer
from service.process.multimodal.multiprocess_utils import BoundedFIFOQueue
from service.process.multimodal.parse_config import ParseConfig
from service.process.multimodal.qwen_process_service import QwenProcessService
from service.process.multimodal.qwen_summary_service import QwenSummaryService
from service.process.multimodal.vstream.utils import disable_torch_init
from service.search.vstream.qwen_search_service_stmopt import QwenSearchService
from service.process.common.client.es_request import bulk_insert_documents

current_dir = os.path.dirname(os.path.abspath(__file__))
logger = logging.get_logger()


def produce_all_frames_worker(file_path, loader, frame_queue, llm_frame_queue, data_buffer, video_fps, play_speed, frame_selection):
    loader.load(file_path, frame_queue, llm_frame_queue, data_buffer, video_fps, play_speed, frame_selection)


# 独立的帧消费进程函数
def consume_frames_worker(input_dict, process_service, frame_queue, data_buffer, nearline_ug_info_queue,
                          nearline_es_queue, proactive_push_queue):
    in_dict = dict(input_dict)
    in_dict.pop("config_dict", None)

    in_dict.update({
        "frame_queue": frame_queue,
        "data_buffer": data_buffer,
        "nearline_ug_info_queue": nearline_ug_info_queue,
        "nearline_es_queue": nearline_es_queue,
        "proactive_push_queue": proactive_push_queue
    })
    process_service.process(in_dict)

def summary_frames_worker(input_dict, summary_service):
    # 加载中间帧caption结果
    interm_captions_path = input_dict["config_dict"]['event_caption_engine']['index_path'] + "scene_caption_results.json"
    if os.path.exists(interm_captions_path):
        with open(interm_captions_path, "r", encoding="utf-8") as f:
            memory_buffer = json.load(f)
        input_dict["inter_captions"] = memory_buffer
    else:
        input_dict["inter_captions"] = []

    # 执行摘要处理
    return summary_service.process(input_dict)

def init_params(ip):
    if ip == "122":
        model_root_path = "/data/yjx/code/Flash-VStream/"
    elif ip == "127":
        model_root_path = "/opt/huawei/data2/yjx/projects/Flash-VStream/"
    else:
        raise ValueError("ip error.")
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=str, default="/home/users/nus/e0970163/scratch/models/Qwen2.5-Omni-7B")
    parser.add_argument("--vision-model-path", type=str, default="/home/users/nus/e0970163/scratch/models/ViT-L-14.pt")
    parser.add_argument("--model-base", type=str, default=None)
    parser.add_argument("--image-file", type=str, default=None)
    # parser.add_argument("--video-file", type=str,
    #                     default="/data/yjx/code/Flash-VStream/data/eval_video/vstream-realtime/movie/mixkit-preparing-a-bowl-with-yogurt-and-fruit-43925-hd-ready.mp4")
    parser.add_argument("--video_name", type=str,
                        default="mixkit-preparing-a-bowl-with-yogurt-and-fruit-43925-hd-ready")
    parser.add_argument("--device-vision", type=str, default="cuda:0")
    parser.add_argument("--device-llm", type=str, default="cuda")
    parser.add_argument("--conv-mode", type=str, default="vicuna_v1")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--load-8bit", action="store_true")
    parser.add_argument("--load-4bit", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--log-file", type=str,
                        default=model_root_path + "data/eval_video/vstream-realtime/movie/realtime_cli.log")
    parser.add_argument("--use_1process", action="store_true")
    parser.add_argument("--video_max_frames", type=int, default=1200)
    parser.add_argument("--video_fps", type=float, default=1.0)
    parser.add_argument("--play_speed", type=float, default=1.0)
    parser.add_argument("--display_img", type=str, choices=["text", "vector"], default="vector")
    parser.add_argument("--frame_selection", type=str, choices=["uniform", "pixelDiff", "opticalFlow"], default="uniform")
    args = parser.parse_args()

    input_dict = {
        "debug": True,
        "scene": {
            "name": "vedio",
        },
        "args": args
    }
    return args, input_dict


# 但请确保所有多进程相关的代码都在__main__下，包括 Queue 的创建。 !!!!
if __name__ == "__main__":

    try:
        # 配置代理信息
        # os.environ["http_proxy"] = "http://10.155.97.225:3128"
        # os.environ["https_proxy"] = os.environ["http_proxy"]
        # os.environ["no_proxy"] = "localhost,127.0.0.1"

        # os.environ["CUDA_VISIBLE_DEVICES"] = "0"

        args, input_dict = init_params(ip="127")

        embedding_file = os.path.join(current_dir, "{}-video_embedding.bin".format(int(time.time())))

        # load & process
        yaml_config_path = ParseConfig.parse_config("dev", {"dev": "offline_config.yaml"})
        yaml_config = Config(config_file_path=yaml_config_path)
        config_dict = yaml_config.get_final_config()
        event_id = int(time.time() * 1000)
        config_dict['event_id'] = event_id

        process_service = QwenProcessService(args, config_dict)
        summary_service = QwenSummaryService(args, config_dict)

        # search
        search_service = QwenSearchService(config_dict, args, embedding_file=embedding_file)

        torch.multiprocessing.set_start_method('spawn', force=True)
        disable_torch_init()

        # # ---------------串行------------------
        # file = "/opt/huawei/data2/atd/code/StreamingQA/data/car/video/test1.mp4"
        # video_fps = 2
        # play_speed = 1

        # loader = VideoLoaderBuffer()
        # frame_queue = Queue(maxsize=1000)
        # llm_frame_queue = deque(maxlen=32)
        # vector_faiss = faiss.IndexFlatIP(768)
        # data_buffer = deque(maxlen=3000)
        # proactive_push_queue = deque(maxlen=32)
        # nearline_ug_info_queue = None
        # nearline_es_queue = None
        # produce_all_frames_worker(file, loader, frame_queue, llm_frame_queue, data_buffer, video_fps, play_speed, args.frame_selection)
        # consume_frames_worker(input_dict, process_service, frame_queue, data_buffer, nearline_ug_info_queue, \
        #                       nearline_es_queue, proactive_push_queue, vector_faiss)
        # question = "车子的车牌号是多少?"
        # index_path = config_dict['faiss_engine']['index_path']
        # config_dict['event_id'] = int(time.time() * 1000)
        # if os.path.exists(index_path):
        #     vector_faiss = faiss.read_index(index_path)
        # input_dict["config_dict"] = config_dict
        # summary_result = summary_frames_worker(input_dict, summary_service)
        # summary_result['event_id'] = config_dict['event_id']
        # interm_captions_path = input_dict["config_dict"]['event_caption_engine']['index_path'] + "scene_caption_results.json"
        # if os.path.exists(interm_captions_path):
        #     os.remove(interm_captions_path)
        # answer = search_service.get_answer(args, question, llm_frame_queue, vector_faiss, process_service.model_kwargs.get("model"))
        # logger.info(answer)

        # # ---------------并行------------------
        file = "/data2/xiaoneng/streaming/Flash-VStream/assets/f562f1ab-0091-45a0-9e66-4de21d820675.mp4"
        video_fps = 1
        play_speed = 1
        input_dict["video_path"] = file

        loader = VideoLoaderBuffer()
        frame_queue = Queue(maxsize=1000)

        # 创建 Manager 实例并初始化共享资源
        manager = mp.Manager()
        shared_list = manager.list()
        shared_lock = manager.Lock()

        # 创建固定长度的 FIFO 队列
        llm_frame_queue = BoundedFIFOQueue(maxsize=32, manager_list=shared_list, manager_lock=shared_lock)

        # 创建 Manager 实例并初始化共享资源
        manager = mp.Manager()
        shared_list = manager.list()
        shared_lock = manager.Lock()

        # 创建固定长度的 FIFO 队列
        data_buffer = BoundedFIFOQueue(maxsize=3000, manager_list=shared_list, manager_lock=shared_lock)

        # 创建 Manager 实例并初始化共享资源
        manager = mp.Manager()
        shared_list = manager.list()
        shared_lock = manager.Lock()

        # 创建固定长度的 FIFO 队列
        proactive_push_queue = BoundedFIFOQueue(maxsize=32, manager_list=shared_list, manager_lock=shared_lock)

        nearline_ug_info_queue = None
        nearline_es_queue = None

        produce = Process(
            target=produce_all_frames_worker,
            args=(file, loader, frame_queue, llm_frame_queue, data_buffer, video_fps, play_speed, args.frame_selection),
            daemon=True
        )
        produce.start()

        consumer_process = Process(
            target=consume_frames_worker,
            args=(input_dict, process_service, frame_queue, data_buffer, nearline_ug_info_queue,
                  nearline_es_queue, proactive_push_queue),
            daemon=True
        )
        consumer_process.start()
        consumer_process.join()

        # ==== 单进程版本：不再使用 multiprocessing.Process ====
        input_dict["config_dict"] = config_dict
        summary_result = summary_frames_worker(input_dict, summary_service)
        print(f"事件分类结果: {summary_result}, event_id: {event_id}")
        interm_captions_path = input_dict["config_dict"]['event_caption_engine'][
                                   'index_path'] + "scene_caption_results.json"
        if os.path.exists(interm_captions_path):
            os.remove(interm_captions_path)
            print(f"Deleted: {interm_captions_path}")
        
        ##########################写入UG Index################################
        write_url = config_dict.get("es_ug_mock").get("url")    
        write_index = config_dict.get("es_ug_mock").get("index")
        write_summary = []
        write_summary.append({
            "caption": "```json\n" +
                        json.dumps(summary_result, ensure_ascii=False, indent=2) +
                        "\n```"
        })
        result = bulk_insert_documents(
            host_url=write_url,
            index_name=write_index,
            documents=write_summary,
        )

        if result is not None:
            logger.info(f"成功插入到{write_index} 索引，成功插入文档数量: {result.get('items', []) and len(result['items'])}")
        else:
            logger.error(f"未能插入文档到 {write_index} 索引")
        
        # while True:
        #     time.sleep(10)
        #     question = "画面发生了什么事情？"            
        #     for answer, image_answer, caption_results, ug_recall_results in search_service.get_answer(
        #         args, question, llm_frame_queue, process_service.model_kwargs.get("model")
        #     ):
        #         pass
        #     logger.info("answer={},caption_results={}, ug_recall_results={}".format(
        #         answer, caption_results, ug_recall_results))

    except Exception as e:
        logger.error(traceback.format_exc())
    logger.info("All processes finished.")
