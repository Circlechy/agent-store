import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
import traceback
import warnings
import random

import gradio as gr

from doc_process.utils import logging
from service.qa.app.entry import Entry

warnings.filterwarnings("ignore", message="Could not get documentation group for")
# 关闭Gradio的分析
os.environ["GRADIO_ANALYTICS_ENABLED"] = "false"

logger = logging.get_logger()
current_dir = os.path.dirname(os.path.abspath(__file__))


class OnlineQaApp:
    def __init__(self, entry):
        self.entry = entry
        def lowercase_file_extension(filename):
            name, ext = os.path.splitext(filename)
            return name + ext.lower()

        demo_video_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        demo_video_dir = os.path.join(demo_video_dir, "data", "demo_videos") #TODO
        
        demo_video_paths = sorted(os.listdir(demo_video_dir))
        demo_video_paths = [video_path for video_path in demo_video_paths if (os.path.isfile(os.path.join(demo_video_dir, video_path)) and lowercase_file_extension(video_path).endswith(".mp4"))]
        demo_video_paths = [os.path.join(demo_video_dir, video_path) for video_path in demo_video_paths]

        def generate_video_generator():
            current_index = 0
            while True:
                yield demo_video_paths[current_index % len(demo_video_paths)]
                current_index += 1

        self.video_generator = generate_video_generator()

    def get_next_video(self):
        return next(self.video_generator)

    def build_gradio_app(self):
        with (gr.Blocks(theme=gr.themes.Soft(), css="""
        #main-col {height: 600px;}
        #video-box { 
            border-radius: 18px; 
            overflow: hidden; 
            box-shadow: 0 4px 24px #e0e7ef; 
            margin-bottom: 18px;
            width: 900;             /* 设置固定宽度 */
            height: 580px;            /* 设置固定高度 */
            max-width: 100%;          /* 防止超出父容器 */
        } 
        #demo-video-box { 
            border-radius: 6px; 
            overflow: hidden; 
            box-shadow: 0 4px 24px #e0e7ef; 
            margin-bottom: 18px;
            width: 100%;
            height: 610.4px;
            max-width: 100%;
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
        # #read_index_data_box textarea { 
        #     height: 500px !important; 
        # }
        # #read_ug_info_box textarea { 
        #     height: 200px !important; 
        # }
        #read_index_data_box {
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
        #read_ug_info_box {
            border: 1px solid var(--input-border-color, #d9d9d9);    
            border-radius: var(--input-radius, 6px);
            background: var(--input-background, #fff);
            padding: 8px 12px;
            height: 250px;              
            overflow-y: auto;              /* 超出就滚动 */
            font-family: inherit;          /* 继承页面字体 */
            white-space: pre-wrap;         /* 保留换行 */
            box-sizing: border-box;
        }
        #read_index_data_box::before {
            content: "读取ES数据";       /* 要显示的文字 */
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
        #read_ug_info_box::before {
            content: "读取UG数据";       /* 要显示的文字 */
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
        """) as demo):
            gr.Markdown("""
            # 🎬 流式记忆demo  运行态
            <span style='color: #666; font-size:18px;'>上传你的视频，实时提问</span>
            """, elem_id="title")
            with gr.Row(elem_id="main-col"):
                with gr.Column(scale=1):
                    demo_video = gr.Video(value=self.get_next_video(), interactive=False, autoplay=True, loop=False, elem_id="demo-video-box")
                    demo_video.end(fn=self.get_next_video, inputs=[], outputs=[demo_video])

                with gr.Column(scale=1, min_width=420):
                    chat_box = gr.Chatbot(
                        elem_id="chat-box",
                        show_label=False,
                    )

                    question = gr.Textbox(placeholder="请输入你想问的问题...", label=None, lines=2,
                                          elem_id="question-input")
                    with gr.Row():
                        ask_btn = gr.Button("提问", variant="primary")
                        prompt_switch = gr.Checkbox(value=False, label="隐私过滤", elem_id="prompt-switch")

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

            def handle_ask(video_url, question, history):
                logger.info(
                    f"[主程序] handle_ask被调用, video_url={video_url}, question={question}, history_len={len(history) if history else 0}")
                # if not video_url:
                #     return gr.update(), history + [["请先上传视频", ""], [None]], gr.update(value=None)
                if not question.strip():
                    return gr.update(), history + [["请输入问题", ""], [None]], gr.update(value=None)
                # answer = self.search_service.get_answer(self.args, question)
                answer, image_answer, caption_results, ug_recall_results = self.entry.search_service.get_answer(
                    self.entry.args,
                    question,
                    self.entry.llm_frame_queue,
                    self.entry.process_service.model_kwargs.get("model"))
                model_reply = f"{answer}"
                history = history + [[question, model_reply]]
                # 返回时仅需提供图片列表即可
                return gr.update(value=""), history, image_answer[:2], "\n".join(caption_results[:2]), "\n".join(
                    ug_recall_results[:2])

            def handle_ask_stream(video_url, question, history, prompt_switch: bool):
                # 0️⃣ 基本校验
                if not question.strip():
                    yield gr.update(), history + [["请输入问题", ""]], gr.update(), None, None
                    return
                # 1️⃣ 先把用户提问 push 到 history（占位回答为空）
                history = history + [[question, ""]]
                yield gr.update(value=""), history, None, "", ""  # 先刷一次，让气泡出现
            
                # 2️⃣ 不断拉取流式 token
                for partial, imgs, caps, ugs in self.entry.search_service.get_answer(
                        self.entry.args, question, self.entry.llm_frame_queue,
                        self.entry.process_service.model_kwargs.get("model"), prompt_switch):
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
                inputs=[video_url_state, question, chat_box, prompt_switch],
                outputs=[question, chat_box, result_gallery, read_index_data_box, read_ug_info_box],
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
        app = OnlineQaApp(entry)
        app.run()
    except Exception:
        logger.error(traceback.format_exc())
