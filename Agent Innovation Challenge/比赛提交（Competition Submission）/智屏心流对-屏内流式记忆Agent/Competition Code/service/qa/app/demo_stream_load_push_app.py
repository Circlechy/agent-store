import os
import traceback
import warnings
from collections import deque

import faiss
import gradio as gr
from gradio import Timer
from torch.multiprocessing import Queue, Process

from doc_process.utils import logging
from service.process.common.client.es_request import delete_all_documents_in_index
from service.process.multimodal.loaders.socket_server import socket_server
from service.process.multimodal.loaders.stream_loader_buffer import StreamLoaderBuffer
from service.process.multimodal.utils.image_utils import base64_to_image
from service.qa.app.entry import Entry
from service.qa.app.utils import delete_directory
from service.qa.serve.qwen_local_service import produce_all_frames_worker, consume_frames_worker

warnings.filterwarnings("ignore", message="Could not get documentation group for")
# 关闭Gradio的分析
os.environ["GRADIO_ANALYTICS_ENABLED"] = "false"

logger = logging.get_logger()
current_dir = os.path.dirname(os.path.abspath(__file__))


class StreamLoadPushApp:
    def __init__(self, entry):
        self.entry = entry
        # ---------------push---------------
        self.push_dict = {
            "push_info": deque(maxlen=5),
            "ug_infos": deque(maxlen=5),
            "segments_file": deque(maxlen=5),
            "frame_base64_segments": deque(maxlen=5),
        }

    def get_proactive_push_data(self, key):
        # 更新缓存
        # todo: 加锁 防止多个组件同时访问导致资源竞争问题
        if self.entry.proactive_push_queue and not self.entry.proactive_push_queue.empty():
            try:
                push_info, ug_infos, segments_file, frame_base64_segments = self.entry.proactive_push_queue.get()
                self.push_dict["push_info"].append(push_info)
                self.push_dict["ug_infos"].append(ug_infos)
                self.push_dict["segments_file"].append(segments_file)
                self.push_dict["frame_base64_segments"].append(frame_base64_segments)
            except Exception:
                logger.error(traceback.format_exc())

        # 从缓存中取值
        if self.push_dict.get(key):
            value = self.push_dict.get(key).popleft()
            if key == "frame_base64_segments":
                value = base64_to_image(value)
            logger.info("get_proactive_push_data(),key={},value={}".format(key, value))
            return value

        elif key == "push_info":
            return ""
        elif key == "ug_infos":
            return ""
        elif key == "segments_file":
            return "/data01/atd/code/StreamingQA3/data/segments/litchi.mp4"
        elif key == "frame_base64_segments":
            return gr.update(value=None)
        else:
            logger.error("unknown key={}".format(key))

    def get_proactive_push_info(self):
        return self.get_proactive_push_data("push_info")

    def get_proactive_ug_infos(self):
        return self.get_proactive_push_data("ug_infos")

    def get_proactive_segments_file(self):
        return self.get_proactive_push_data("segments_file")

    def get_proactive_frame_base64_segments(self):
        return self.get_proactive_push_data("frame_base64_segments")

    def get_nearline_es_queue_data(self):
        return self.entry.nearline_es_queue.get() if not self.entry.nearline_es_queue.empty() else ""

    def get_nearline_ug_info_queue_data(self):
        return self.entry.nearline_ug_info_queue.get() if not self.entry.nearline_ug_info_queue.empty() else ""

    def handle_upload(self):
        logger.info(f"[主程序] handle_upload被调用, streaming")
        # ---------------并行------------------

        vector_faiss = faiss.IndexFlatIP(768)

        consumer_process = Process(
            target=consume_frames_worker,
            args=(self.entry.input_dict, self.entry.process_service, self.entry.frame_queue,
                  self.entry.data_buffer,
                  self.entry.nearline_ug_info_queue, self.entry.nearline_es_queue,
                  self.entry.proactive_push_queue,
                  vector_faiss),
            daemon=True
        )
        consumer_process.start()

        self.video_frame_global = Queue(maxsize=1000)
        send = Process(
            target=socket_server,
            args=(self.video_frame_global,),
            daemon=True
        )
        send.start()

        self.loader = StreamLoaderBuffer()
        produce = Process(
            target=produce_all_frames_worker,
            args=(self.video_frame_global, self.loader, self.entry.frame_queue, self.entry.llm_frame_queue,
                  self.entry.data_buffer, 3, 1, self.entry.args.frame_selection),
            daemon=True
        )
        produce.start()

    def build_gradio_app(self):
        with gr.Blocks(theme=gr.themes.Soft(), css="""
        #main-col {height: 600px;}
        #video-box { 
            border-radius: 18px; 
            overflow: hidden; 
            box-shadow: 0 4px 24px #e0e7ef; 
            margin-bottom: 18px;
            width: 900px;             /* 设置固定宽度 */
            height: 600px;            /* 设置固定高度 */
            max-width: 100%;          /* 防止超出父容器 */
        }
        #chat-box { 
            height: 500px; 
            overflow-y: auto; 
            background: #f9f9f9; 
            border-radius: 18px; 
            padding: 20px; 
            margin-bottom: 18px; 
            box-shadow: 0 2px 12px #f0f2f8;
        }
        #question-input textarea { 
            border-radius: 10px; 
            font-size: 16px;
        }
        #title { 
            margin-bottom: 32px;
        }
        #index_data-output textarea { 
            height: 500px !important; 
        }
        #write_index_data_box {
            border: 1px solid var(--input-border-color, #d9d9d9);    
            border-radius: var(--input-radius, 6px);
            background: var(--input-background, #fff);
            padding: 8px 12px;
            height: 400px;                 
            overflow-y: auto;              /* 超出就滚动 */
            font-family: inherit;          /* 继承页面字体 */
            white-space: pre-wrap;         /* 保留换行 */
            box-sizing: border-box;
        }
        #write_ug_info_box {
            border: 1px solid var(--input-border-color, #d9d9d9);    
            border-radius: var(--input-radius, 6px);
            background: var(--input-background, #fff);
            padding: 8px 12px;
            height: 150px;                 
            overflow-y: auto;              /* 超出就滚动 */
            font-family: inherit;          /* 继承页面字体 */
            white-space: pre-wrap;         /* 保留换行 */
            box-sizing: border-box;
        }
        #write_index_data_box::before {
            content: "写入ES数据";       /* 要显示的文字 */
            display: inline-block;           /* 让背景刚好包住文字 */
            font-weight: 600;
            font-size: 16px;
            margin-bottom: 4px;
            color: #1677ff;                  /* 纯蓝字体（Ant Design 蓝）*/
            background: #e6f4ff;             /* 同色系浅底 */
            padding: 2px 6px;                /* 内边距让背景框更明显 */
            border-radius: 4px;              /* 小圆角 */
            margin-bottom: 6px;              /* 与正文留空 */
        }
        #write_ug_info_box::before {
            content: "关联UG数据";       /* 要显示的文字 */
            display: inline-block;           /* 让背景刚好包住文字 */
            font-weight: 600;
            font-size: 16px;
            margin-bottom: 4px;
            color: #1677ff;                  /* 纯蓝字体（Ant Design 蓝）*/
            background: #e6f4ff;             /* 同色系浅底 */
            padding: 2px 6px;                /* 内边距让背景框更明显 */
            border-radius: 4px;              /* 小圆角 */
            margin-bottom: 6px;              /* 与正文留空 */
        }
        """) as demo:
            gr.Markdown("""
            # 🎬 流式记忆demo  实时解析
            <span style='color: #666; font-size:18px;'>上传你的视频，实时提问</span>
            """, elem_id="title")
            # with gr.Row(elem_id="main-col"):
            #     with gr.Column(scale=1, min_width=400):  # 限制列的最大宽度
            #         video_file = gr.Video(label="", interactive=True, elem_id="video-box")

            video_url_state = gr.State("")
            # 在gr.Row()组件下添加图片显示区域
            with gr.Column():
                # 创建Textbox组件，设置every参数
                push_info_box = gr.Textbox(
                    label="主动推送",
                    value=self.get_proactive_push_info,
                    every=Timer(value=3),  # 绑定定时器[1,2](@ref)
                    elem_id="push_info_box",
                    # interactive=False,
                    # placeholder=""
                )
                push_gallery = gr.Gallery(label="命中的视频帧",
                                          columns=7,
                                          # preview=True,
                                          value=self.get_proactive_frame_base64_segments,
                                          every=Timer(value=3),  # 绑定定时器[1,2](@ref)
                                          elem_id="push_gallery",
                                          object_fit="contain",
                                          height=500)
                # write_index_data_box = gr.Markdown(
                #     label="ES索引数据",
                #     value=self.get_nearline_es_queue_data,
                #     every=Timer(value=3),
                #     elem_id="write_index_data_box"
                # )
                # write_ug_info_box = gr.Markdown(
                #     label="ug数据",
                #     value=self.get_nearline_ug_info_queue_data,
                #     every=Timer(value=3),  # 绑定定时器[1,2](@ref)
                #     elem_id="write_ug_info_box"
                # )
                chat_box = gr.Chatbot(
                    elem_id="chat-box",
                    show_label=False,
                )

                question = gr.Textbox(placeholder="请输入你想问的问题...", label=None, lines=2,
                                      elem_id="question-input")
                with gr.Row():
                    ask_btn = gr.Button("提问", variant="primary")
            video_url_state = gr.State("")
            # 在gr.Row()组件下添加图片显示区域
            with gr.Row():
                with gr.Column():
                    read_index_data_box = gr.Markdown(
                        label="ES索引数据",
                        elem_id="read_index_data_box"
                    )
                    read_ug_info_box = gr.Markdown(
                        label="ug数据",
                        elem_id="read_ug_info_box"
                    )
                # 定义Gallery组件用于展示多张图片
                result_gallery = gr.Gallery(label="命中的视频帧",
                                            columns=3,
                                            preview=True,
                                            object_fit="contain",
                                            height=600)
            def handle_ask_stream(video_url, question, history):
                # 0️⃣ 基本校验
                if not question.strip():
                    yield gr.update(), history + [["请输入问题", ""]], gr.update(), None, None
                    return
                # 创建向量检索库
                vector_faiss = faiss.IndexFlatIP(768)
                index_path = self.entry.config_dict['faiss_engine']['index_path']
                if os.path.exists(index_path):
                    vector_faiss = faiss.read_index(index_path)
                # 1️⃣ 先把用户提问 push 到 history（占位回答为空）
                history = history + [[question, ""]]
                yield gr.update(value=""), history, None, "", ""  # 先刷一次，让气泡出现

                # 2️⃣ 不断拉取流式 token
                for partial, imgs, caps, ugs in self.entry.search_service.get_answer(
                        self.entry.args, question, self.entry.llm_frame_queue, vector_faiss,
                        self.entry.process_service.model_kwargs.get("model")):
                    history[-1][1] = partial  # 更新最后一条回复

                    # 图片 / 召回信息只有最后一次才非空；否则 keep None
                    yield (
                        gr.update(value=""),  # 清空输入框
                        history,  # 刷新对话
                        imgs if imgs else gr.update(),  # Gallery
                        "\n".join(caps) if caps else gr.update(),  # ES 区
                        "\n".join(ugs) if ugs else gr.update()  # UG 区
                    )

            # # 修改按钮绑定逻辑
            # ask_btn.click(
            #     handle_ask,
            #     inputs=[video_url_state, question, chat_box],
            #     outputs=[question, chat_box, result_gallery, read_index_data_box, read_ug_info_box]  # 增加图片输出
            # )

            ask_btn.click(
                fn=handle_ask_stream,  # 生成器函数
                inputs=[video_url_state, question, chat_box],
                outputs=[question, chat_box, result_gallery, read_index_data_box, read_ug_info_box],
            )
        self.handle_upload()
        return demo

    def run_service(self):
        self.handle_upload()

    def run(self):
        demo = self.build_gradio_app()
        demo.launch(
            debug=True,
            server_port=8074,  # 使用备用端口
            server_name="0.0.0.0",  # 允许所有网络接口访问
        )


if __name__ == "__main__":

    try:
        # # 清空ES短期记忆信息：
        # host = "http://10.50.91.196:9200"
        # index_name = "short_term"
        # result = delete_all_documents_in_index(
        #     host_url=host,
        #     index_name=index_name,
        # )
        # # 处理结果
        # if result is not None:
        #     print(f"成功删除 {index_name} 索引中的所有文档:{result.get('deleted', 0)}")
        # else:
        #     print(f"未能清空 {index_name} 索引")
        #
        # # 清空faiss索引
        # delete_directory("data/image_cache")

        entry = Entry("realtime")
        app = StreamLoadPushApp(entry)
        # app.run()
        app.run()
    except Exception:
        logger.error(traceback.format_exc())
