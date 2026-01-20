import traceback

import gradio as gr

from service.qa.app.demo_qa_app import OnlineQaApp
from service.qa.app.demo_stream_load_push_app import StreamLoadPushApp
from service.qa.app.entry import Entry, logger


if __name__ == "__main__":
    try:
        entry = Entry("realtime")
        with gr.Blocks() as demo:
            StreamLoadPushApp(entry).build_gradio_app().render()
        with demo.route("Second Page"):
            OnlineQaApp(entry).build_gradio_app().render()
        demo.launch(
            debug=True,
            server_port=8084,  # 使用备用端口
            server_name="0.0.0.0",  # 允许所有网络接口访问
        )
    except Exception:
        logger.error(traceback.format_exc())
