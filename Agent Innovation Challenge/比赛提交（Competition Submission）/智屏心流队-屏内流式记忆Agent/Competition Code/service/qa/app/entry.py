
import os
import time
import traceback
import warnings

import faiss
import gradio as gr
import torch
import torch.multiprocessing as mp
from gradio import Timer
from torch.multiprocessing import Queue, Process

from doc_process.config_repository.config import Config
from doc_process.utils import logging
from service.process.multimodal.loaders.video_loader_buffer import VideoLoaderBuffer
from service.process.multimodal.multiprocess_utils import BoundedFIFOQueue
from service.process.multimodal.parse_config import ParseConfig
from service.process.multimodal.qwen_process_service import QwenProcessService
from service.process.multimodal.vstream.utils import disable_torch_init
from service.qa.app.env_config import ENV_YAML_DICT
from service.qa.app.ug_write_config import UG_WRITE_DICT
from service.qa.serve.qwen_local_service import init_params, produce_all_frames_worker, consume_frames_worker, summary_frames_worker
from service.search.vstream.qwen_search_service_stmopt import QwenSearchService
from service.process.multimodal.qwen_summary_service import QwenSummaryService

logger = logging.get_logger()
current_dir = os.path.dirname(os.path.abspath(__file__))
class Entry:
    def __init__(self, env_name):
        self.env_name = env_name
        self.init_service()
        self.init_queue_status()
        self.init_nearline_statue()

    def init_service(self):
        # 配置代理信息
        # os.environ["http_proxy"] = "http://10.155.97.225:3128"
        # os.environ["https_proxy"] = os.environ["http_proxy"]
        # os.environ["no_proxy"] = "localhost,127.0.0.1,.huawei.com"

        os.environ["CUDA_VISIBLE_DEVICES"] = "0"

        # 如果涉及 CUDA 张量共享（如 GPU 计算），fork 可能导致死锁或资源竞争。此时应使用 spawn 或 forkserver。
        torch.multiprocessing.set_start_method('spawn', force=True)
        disable_torch_init()

        self.args, self.input_dict = init_params(ip="127")

        # load & process
        yaml_config_path = ParseConfig.parse_config(self.env_name, ENV_YAML_DICT)
        # yaml_config_path = ParseConfig.parse_config("offline", ENV_YAML_DICT)
        yaml_config = Config(config_file_path=yaml_config_path)
        self.config_dict = yaml_config.get_final_config()
        self.event_id = int(time.time() * 1000)
        self.config_dict['event_id'] = self.event_id

        self.process_service = QwenProcessService(self.args, self.config_dict)

        # search
        self.search_service = QwenSearchService(self.config_dict, self.args)
        self.input_dict["config_dict"] = self.config_dict
        self.summary_service  = QwenSummaryService(self.args, self.config_dict)

    def init_nearline_statue(self):
        self.ug_write_dict = UG_WRITE_DICT
        self.input_dict["ug_write_dict"] = self.ug_write_dict

    def init_queue_status(self):
        # 创建 Manager 实例并初始化共享资源
        manager = mp.Manager()
        shared_list = manager.list()
        shared_lock = manager.Lock()
        self.nearline_ug_info_queue = BoundedFIFOQueue(
            maxsize=30, manager_list=shared_list,
            manager_lock=shared_lock)

        # 创建 Manager 实例并初始化共享资源
        manager = mp.Manager()
        shared_list = manager.list()
        shared_lock = manager.Lock()
        self.nearline_es_queue = BoundedFIFOQueue(
            maxsize=30, manager_list=shared_list,
            manager_lock=shared_lock)

        self.loader = VideoLoaderBuffer()
        self.frame_queue = Queue(maxsize=1000)

        # 创建 Manager 实例并初始化共享资源
        manager = mp.Manager()
        shared_list = manager.list()
        shared_lock = manager.Lock()

        # 创建固定长度的 FIFO 队列
        self.llm_frame_queue = BoundedFIFOQueue(maxsize=32, manager_list=shared_list,
                                                manager_lock=shared_lock)

        # 创建 Manager 实例并初始化共享资源
        manager = mp.Manager()
        shared_list = manager.list()
        shared_lock = manager.Lock()

        # 创建固定长度的 FIFO 队列
        self.data_buffer = BoundedFIFOQueue(maxsize=300, manager_list=shared_list,
                                            manager_lock=shared_lock)

        # 创建 Manager 实例并初始化共享资源
        manager = mp.Manager()
        shared_list = manager.list()
        shared_lock = manager.Lock()
        # 创建固定长度的 FIFO 队列
        self.proactive_push_queue = BoundedFIFOQueue(maxsize=10, manager_list=shared_list,
                                                     manager_lock=shared_lock)


