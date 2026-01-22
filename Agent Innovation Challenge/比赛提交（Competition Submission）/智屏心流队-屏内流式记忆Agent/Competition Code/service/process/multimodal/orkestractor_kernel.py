import time
import traceback
from abc import ABC
from typing import Dict
from collections import defaultdict
import re
from torch.multiprocessing import Queue

from doc_process.context.base_schema import Context
from doc_process.context.multimodal_schema import MultimodalContext, MultimodalStream, ExecuteType
from doc_process.utils import logging

logger = logging.get_logger()


class BaseOrchestrator(ABC):
    """OrchestratorKernel"""

    def parse_input(self, input_dict: Dict) -> Dict:
        """
        对input预处理
        """

    def transform_input(self, input_dict: Dict, context: Context):
        """
        从input构造context
        """

    def forward(self, input_dict: Dict):
        """
        Orchestrator执行入口
        """

    def call_pipeline(self, context: Context):
        """
        执行pipeline
        """

    def transform_output(self, context: Context) -> dict:
        """
        从context构造output
        """


class MultimodalProcessOrchestrator(BaseOrchestrator):
    """MultimodalProcessOrchestrator"""

    def parse_input(self, input_dict: Dict) -> Dict:
        """
        对input预处理
        """
        return input_dict

    def transform_input(self, input_dict: Dict, context: Context):
        """
        从input构造context
        """
        context.update_input_kwargs_with_dict(input_dict)
        debug: bool = input_dict.get("debug", None)
        if debug is not None:
            context.set_verbose(debug)

        if context.get_verbose():
            logging.set_level_debug()
        else:
            logging.set_level_info()

    def transform_output(self, context: Context) -> dict:
        """
        从context 构造response
        """
        if not context.get_verbose():
            context.get_pipeline_response().pop("cost_time")
        return context.get_pipeline_response()


class UpdateLocalVideoOrchestrator(MultimodalProcessOrchestrator):
    """UpdateLocalVideoOrchestrator"""

    def __init__(self, config_dict: Dict, small_pipeline, big_pipeline):
        super().__init__()
        self.pipeline_small = small_pipeline     # batch=3 每次都跑
        self.pipeline_big   = big_pipeline       # 聚满 30 帧才跑
        self.batch_size = 3  # 允许运行时动态调整批次大小
        self._loop_counter  = 0
        self._agg_frames    = []                 # 收集 30 帧给大算子
        self._cost_sum = defaultdict(float)
        self._frame_sum = defaultdict(int)
    def forward(self, input_dict: Dict) -> dict:
        logger.debug("multimodal process start run")
        start_time = time.time()

        # build context
        context = MultimodalContext()
        input_dict = self.parse_input(input_dict)
        self.transform_input(input_dict, context)

        # call pipeline
        frame_queue: Queue = input_dict.get("frame_queue")
        self.consume_queue(context, frame_queue)

        # ---------- 计算平均耗时 ----------
        avg_cost_time = {}
        for name, total_sec in self._cost_sum.items():
            frames = self._frame_sum[name]
            if frames:
                avg_cost_time[name] = f"{total_sec/frames:.4f}s"
        # 把平均值写入同一个 cost_time 字段，方便日志一并输出
        context.update_cost_time("average_per_frame", avg_cost_time)

        context.update_cost_time("total", "{:.2f}s".format(time.time() - start_time))

        # build response
        logger.info("component_info={}".format(context.get_component_info()))
        logger.info("pipeline_response={}".format(context.get_pipeline_response()))
        response = self.transform_output(context)
        del context
        return response

    def consume_queue(self, context: MultimodalContext, frame_queue):
        logger.info('consume_queue Process: start')

        frame_cnt = 0
        frame_buffer = []  # 帧缓存容器

        while True:
            video_clip = frame_queue.get()
            frame_cnt += 1

            if video_clip is None:  # 结束信号处理
                logger.info('检测到流结束信号')
                # ① 先把不足 batch_size 的残余帧走一遍小批 pipeline
                if frame_buffer:
                    self._process_batch(context, frame_buffer,
                                        frame_cnt - len(frame_buffer))
                # ② 再把聚合的不足 30 帧也跑一次大算子
                if self._agg_frames:               # 还没触发过大算子
                    self._run_big(context)         # ← 就这行
                break
            frame_buffer.append(video_clip)

            # 每累积batch_size帧处理一次
            if len(frame_buffer) == self.batch_size:
                self._process_batch(context, frame_buffer, frame_cnt - self.batch_size + 1)
                frame_buffer = []  # 清空缓冲区

        logger.info('consume_queue Process: end')

    def _process_batch(self, context, buffer, start_idx):
        """批量处理帧的核心逻辑"""
        multimodal_stream = MultimodalStream()

        # 批量添加帧到数据流
        multimodal_stream.get_frame_queue().extend(buffer)
        context.get_multimodal().get_multimodal_streams().append(multimodal_stream)

        # 执行处理管线
        try:
            # ---- 跑小批管线 (3 帧) ----
            self.pipeline_small.run(context=context, stream=multimodal_stream, **context.get_input_kwargs())

            # 更新状态和日志
            multimodal_stream.set_status(ExecuteType.FINISH)
        except Exception as e:
            logger.error(traceback.format_exc())
            multimodal_stream.set_status(ExecuteType.ERROR)

        # ---- 累计帧数 ----
        self._agg_frames.extend(buffer)
        self._loop_counter += 1
        
        if self._loop_counter % 10 == 0:
            self._run_big(context)    
            
        # -------------  累加该批次的算子耗时  ----------------
        cost_time = context.get_pipeline_response().get("cost_time", {})
        frame_cnt_this_batch = len(buffer)

        def _sec(tstr: str) -> float:
            """转 float"""
            return float(re.sub(r"[sS]$", "", tstr))

        for name, t_str in cost_time.items():
            # 跳过 total; 按需要也可统计
            if name == "total":
                continue
            self._cost_sum[name] += _sec(t_str)
            self._frame_sum[name] += frame_cnt_this_batch
        # -----------------------------------------------------------

        logger.info(f"[消费者] 批量消费{len(buffer)}帧，区间[{start_idx}-{start_idx + len(buffer) - 1}]")
        logger.info(f"cost_time={context.get_cost_time()}")
        
    def _run_big(self, context):
        if not self._agg_frames:
            return
        s = MultimodalStream(); s.get_frame_queue().extend(self._agg_frames)
        self.pipeline_big.run(context=context, stream=s, **context.get_input_kwargs())
        logger.info('run long term recognizer')
        self._agg_frames.clear()
