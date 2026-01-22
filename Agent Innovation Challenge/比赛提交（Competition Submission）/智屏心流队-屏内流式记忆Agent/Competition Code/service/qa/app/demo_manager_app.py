import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
import traceback
import warnings

import gradio as gr
from gradio import Timer
from torch.multiprocessing import Process
import json
from doc_process.utils import logging
from service.qa.app.entry import Entry
from service.qa.serve.qwen_local_service import produce_all_frames_worker, consume_frames_worker, summary_frames_worker
from service.process.multimodal.qwen_summary_service import QwenSummaryService
from service.process.common.client.es_request import bulk_insert_documents, delete_all_documents_in_index
import threading

warnings.filterwarnings("ignore", message="Could not get documentation group for")
# 关闭Gradio的分析
os.environ["GRADIO_ANALYTICS_ENABLED"] = "false"

logger = logging.get_logger()
current_dir = os.path.dirname(os.path.abspath(__file__))
# StreamingQA/service/qa/app/demo_manager_app.py

def summary_runner(args_dict, config_dict, ug_queue):
    """
    子进程：重新创建 QwenSummaryService -> 跑摘要 -> 推到 ug_queue
    传入的全部都是 *可 pickle* 的原生对象！
    """
    try:
        # 重新构建 service（避免把大模型实例化后再 pickle）
        summary_service = QwenSummaryService(args_dict, config_dict)

        in_dict = {"config_dict": config_dict}      # summary_frames_worker 只需要这一项
        res = summary_frames_worker(in_dict, summary_service)

        if res:
            ug_queue.put(f"```json\n{json.dumps(res, ensure_ascii=False, indent=2)}\n```")
    except Exception:
        logger.error(traceback.format_exc())
            
class ManagerApp:
    def __init__(self, entry):
        self.is_loaded = False
        self.entry = entry
        self._es_has_new_data = False
        self._es_latest_value   = ""
        # self._ug_event_displayed = False
        self._ug_latest_value = ""
        
    # ====== 新增：工具方法 ======
    def _get_cfg(self, keys):
        """
        从 config_dict 里按候选 key 顺序取 {url, index}，找不到则返回 (None, None)
        """
        cfg = self.entry.config_dict
        for k in keys:
            v = cfg.get(k)
            if isinstance(v, dict) and "url" in v and "index" in v:
                return v["url"], v["index"]
        return None, None

    def _format_to_caption(self, text: str) -> str:
        """
        文本若为合法 JSON，则格式化为 ```json fenced code```；否则原样返回
        """
        if not text:
            return ""
        try:
            obj = json.loads(text)
            return "```json\n" + json.dumps(obj, ensure_ascii=False, indent=2) + "\n```"
        except Exception:
            # 允许手动补充非 JSON 文本
            return text

    def _drain_queue(self, q):
        try:
            while not q.empty():
                q.get()
        except Exception:
            pass

    def get_nearline_es_queue_data(self):
        return self.entry.nearline_es_queue.get() if not self.entry.nearline_es_queue.empty() else ""

    def get_nearline_ug_info_queue_data(self):
        return self.entry.nearline_ug_info_queue.get() if not self.entry.nearline_ug_info_queue.empty() else ""

    def _index_box_value(self):
        q = self.entry.nearline_es_queue
        if not q.empty():
            self._es_latest_value = q.get()
        return self._es_latest_value

    def _ug_box_value(self):
        q = self.entry.nearline_ug_info_queue
        if not q.empty():
            self._ug_latest_value = self.entry.nearline_ug_info_queue.get()
        return self._ug_latest_value 

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
            height: 300px;                 
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
            height: 200px;                 
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
        /* 新增：让两个手动输入框大小与 write_ug_info_box 一致 */
        #manual_es_input textarea, 
        #manual_ug_input textarea {
            border: 1px solid var(--input-border-color, #d9d9d9);
            border-radius: var(--input-radius, 6px);
            background: var(--input-background, #fff);
            padding: 8px 12px;
            height: 200px !important;   /* 与 write_ug_info_box 保持一致 */
            overflow-y: auto;
            font-family: inherit;
            white-space: pre-wrap;
            box-sizing: border-box;
        }
        """) as demo:
            gr.Markdown("""
            # 🎬 流式记忆demo  管理态
            <span style='color: #666; font-size:18px;'>上传你的视频，实时提问</span>
            """, elem_id="title")
            with gr.Row(elem_id="main-col"):
                with gr.Column(scale=1, min_width=400):  # 限制列的最大宽度
                    video_file = gr.Video(label="", interactive=True, elem_id="video-box")

            video_url_state = gr.State("")
#             UG_EVENT_MD = """```json
# {
# "起点": "",
# "地点": "朋友家里",
# "事件描述": "在朋友家里聊天打牌",
# "发生日期": "",
# "持续时间": "",
# "参与人": [
# "带着毛茸茸帽子的朋友"
# ],
# "event_id": 93,
# "type": "social_events"
# }
# ```"""
#             self._es_latest_value   = ""   # 保存索引框最近一次取到的内容
#             self._ug_event_displayed = False  # 是否已经把固定 Markdown 显示过
#             # 在gr.Row()组件下添加图片显示区域
#             def index_box_value():
#                 data = (self.entry.nearline_es_queue.get()
#                         if not self.entry.nearline_es_queue.empty()
#                         else "")
#                 if data:
#                     self._es_latest_value = data
#                 return data

#             def ug_box_value():
#                 # 若索引框已有数据且 Markdown 尚未显示 ⇒ 显示并打标记
#                 if self._es_latest_value and not self._ug_event_displayed:
#                     self._ug_event_displayed = True
#                     return UG_EVENT_MD
#                 # 否则保持现状（空或已显示过）
#                 return UG_EVENT_MD if self._ug_event_displayed else ""
            
            with gr.Column():
                # 创建Textbox组件，设置every参数
                write_index_data_box = gr.Markdown(
                    label="ES索引数据",
                    # value=self.get_nearline_es_queue_data,
                    value=self._index_box_value,
                    every=Timer(value=3),
                    elem_id="write_index_data_box"
                )
                write_ug_info_box = gr.Markdown(
                    label="ug数据",
                    # value=self.get_nearline_ug_info_queue_data,
                    value=self._ug_box_value,
                    every=Timer(value=3),  # 绑定定时器[1,2](@ref)
                    elem_id="write_ug_info_box"
                )
                
            # ====== 新增：手动补充输入与写入/删除按钮 ======
            with gr.Row():
                with gr.Column():
                    manual_es_input = gr.Textbox(
                        label="手动补充 ES 索引数据",
                        placeholder="粘贴或输入 JSON / 文本；将写入 ES 索引",
                        elem_id="manual_es_input",
                        lines=8
                    )
                    with gr.Row():
                        btn_es_write  = gr.Button("写入 ES 索引", variant="primary")
                        btn_es_clear  = gr.Button("清空 ES 索引", variant="stop")

                with gr.Column():
                    manual_ug_input = gr.Textbox(
                        label="手动补充 UG 数据",
                        placeholder="粘贴或输入 JSON / 文本；将写入 UG 索引",
                        elem_id="manual_ug_input",
                        lines=8
                    )
                    with gr.Row():
                        btn_ug_write  = gr.Button("写入 UG 索引", variant="primary")
                        btn_ug_clear  = gr.Button("清空 UG 索引", variant="stop")

            # ====== 写入/删除：后端逻辑 ======
            def write_es_handler(text):
                if not text:
                    return gr.update()  # 不改动输入框
                es_url, es_index = self._get_cfg(["es_short_term"])
                if not es_url or not es_index:
                    logger.error("ES写入失败：未找到配置（es_short_term）")
                    return gr.update()

                caption = self._format_to_caption(text)
                try:
                    result = bulk_insert_documents(
                        host_url=es_url,
                        index_name=es_index,
                        documents=[{"caption": caption}],
                    )
                    if result is not None:
                        logger.info(f"成功插入到{es_index} 索引，成功插入文档数量: {result.get('items', []) and len(result['items'])}")
                    else:
                        logger.error(f"未能插入文档到 {es_index} 索引")
                    # 推到前端展示（每3秒定时器会自动刷新）
                    self.entry.nearline_es_queue.append(caption)
                    self._es_latest_value = caption
                    return gr.update(value="")  # 清空输入框
                except Exception:
                    logger.error(traceback.format_exc())
                    return gr.update()

            def write_ug_handler(text):
                if not text:
                    return gr.update()
                # UG 单独配置优先；找不到则回退到 es_ug_mock
                ug_url, ug_index = self._get_cfg(["es_ug_mock"])
                if not ug_url or not ug_index:
                    logger.error("UG写入失败：未找到配置（es_ug_mock）")
                    return gr.update()

                caption = self._format_to_caption(text)
                try:
                    result_ug = bulk_insert_documents(
                        host_url=ug_url,
                        index_name=ug_index,
                        documents=[{"caption": caption}],
                    )
                    if result_ug is not None:
                        logger.info(f"成功插入到{ug_index} 索引，成功插入文档数量: {result_ug.get('items', []) and len(result_ug['items'])}")
                    else:
                        logger.error(f"未能插入文档到 {ug_index} 索引")
                    # 推到前端展示（每3秒定时器会自动刷新）
                    self.entry.nearline_ug_info_queue.append(caption)
                    self._ug_latest_value = caption
                    return gr.update(value="")
                except Exception:
                    logger.error(traceback.format_exc())
                    return gr.update()

            def clear_es_handler():
                es_url, es_index = self._get_cfg(["es_short_term"])
                if not es_url or not es_index:
                    logger.error("ES清空失败：未找到配置（es_short_term）")
                    return gr.update(value="")  # 清空显示
                try:
                    delete_all_documents_in_index(host_url=es_url, index_name=es_index)
                except Exception:
                    logger.error(traceback.format_exc())
                # 清前端显示队列
                self._drain_queue(self.entry.nearline_es_queue)
                self._es_latest_value = ""
                return gr.update(value="")  # 立即清空右侧 Markdown

            def clear_ug_handler():
                ug_url, ug_index = self._get_cfg(["es_ug_mock"])
                if not ug_url or not ug_index:
                    logger.error("UG清空失败：未找到配置（es_ug_mock）")
                    return gr.update(value="")
                try:
                    delete_all_documents_in_index(host_url=ug_url, index_name=ug_index)
                except Exception:
                    logger.error(traceback.format_exc())
                # 清前端显示队列
                self._drain_queue(self.entry.nearline_ug_info_queue)
                self._ug_latest_value = ""
                return gr.update(value="")

            # ====== 事件绑定 ======
            btn_es_write.click(write_es_handler, inputs=[manual_es_input], outputs=[manual_es_input])
            btn_ug_write.click(write_ug_handler, inputs=[manual_ug_input], outputs=[manual_ug_input])

            # 清空时顺便把右侧 Markdown 置空（立即可见）；定时器之后也会保持为空
            btn_es_clear.click(clear_es_handler, inputs=None, outputs=[write_index_data_box])
            btn_ug_clear.click(clear_ug_handler, inputs=None, outputs=[write_ug_info_box])


            def handle_upload(file: str):
                # if self.entry.is_loaded:
                #     return file
                # self.entry.is_loaded = True
                logger.info(f"[主程序] handle_upload被调用, file={file}")
                if not file:
                    return
                res = {'video_url': file}
                # ---------------并行------------------
                produce = Process(
                    target=produce_all_frames_worker,
                    args=(file, self.entry.loader, self.entry.frame_queue, self.entry.llm_frame_queue,
                          self.entry.data_buffer, 1, 1, self.entry.args.frame_selection),
                    daemon=True
                )
                produce.start()
                consumer_dict = self.entry.input_dict.copy()
                consumer_dict.pop("config_dict", None)
                consumer_process = Process(
                    target=consume_frames_worker,
                    args=(consumer_dict, self.entry.process_service, self.entry.frame_queue,
                          self.entry.data_buffer,
                          self.entry.nearline_ug_info_queue, self.entry.nearline_es_queue,
                          self.entry.proactive_push_queue),
                    daemon=True
                )
                consumer_process.start()
                        
                # # ---------- summary ----------
                # p3 = Process(
                #     target=summary_runner,
                #     args=(
                #         self.entry.args,                      # 只包含简单字段
                #         self.entry.config_dict,               # 纯 dict
                #         self.entry.nearline_ug_info_queue,    # Manager 队列可 pickle
                #     ),
                #     daemon=True,
                # )
                # p3.start()
    # -------------------------------------------------
    # 后台线程：等待 consumer 结束 ➜ 单线程跑 summary
    # -------------------------------------------------
                def summary_after_consumer():
                    # 等 consumer 完全跑完
                    consumer_process.join()

                    # 把 config_dict 塞回去，供 summary 使用
                    in_dict = {"config_dict": self.entry.config_dict}
                    summary_res = summary_frames_worker(in_dict,       # 单线程调用
                                                        QwenSummaryService(self.entry.args,
                                                                        self.entry.config_dict))

                    # 删除中间 caption 缓存文件
                    cap_path = os.path.join(
                        self.entry.config_dict['event_caption_engine']['index_path'],
                        "scene_caption_results.json"
                    )
                    if os.path.exists(cap_path):
                        os.remove(cap_path)

                    # ----------- 写入 ES  -----------
                    url   = self.entry.config_dict["es_ug_mock"]["url"]
                    index = self.entry.config_dict["es_ug_mock"]["index"]
                    result = bulk_insert_documents(
                        host_url=url,
                        index_name=index,
                        documents=[{"caption": "```json\n" +
                        json.dumps(summary_res, ensure_ascii=False, indent=2) +
                        "\n```"}],
                    )
                    if result is not None:
                        logger.info(f"成功插入到{index} 索引，成功插入文档数量: {result.get('items', []) and len(result['items'])}")
                    else:
                        logger.error(f"未能插入文档到 {index} 索引")
                    # ----------- 推到前端队列，让 <Markdown> 显示 -----------
                    markdown = f"```json\n{json.dumps(summary_res, ensure_ascii=False, indent=2)}\n```"
                    # BoundedFIFOQueue 用 append
                    self.entry.nearline_ug_info_queue.append(markdown)

                threading.Thread(target=summary_after_consumer, daemon=True).start()
                return file

            video_file.upload(
                handle_upload,
                inputs=[video_file],
                outputs=[video_url_state]
            )

        return demo

    def run(self):
        demo = self.build_gradio_app()
        demo.launch(
            debug=True,
            server_port=8095,  # 使用备用端口
            server_name="0.0.0.0",  # 允许所有网络接口访问
        )


if __name__ == "__main__":

    try:
        entry = Entry("offline")
        app = ManagerApp(entry)
        app.run()
    except Exception:
        logger.error(traceback.format_exc())
