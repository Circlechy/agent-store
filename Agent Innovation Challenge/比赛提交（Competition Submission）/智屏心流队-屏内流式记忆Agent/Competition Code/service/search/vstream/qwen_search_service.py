import time
import traceback
from datetime import datetime
from PIL import Image
import os

import torch
from PIL import Image
from transformers import TextStreamer
import cn_clip.clip as clip
import torch.nn.functional as F

from doc_process.utils import logging
from service.process.multimodal.utils.file_utils import FileStorageWithLock
from service.process.multimodal.utils.ug_utils import UgClient
from service.search.common_search_utils import parse_img
from service.search.metaengine.handler.recall import text_recall
# from search.flash_vstream1.mm_utils import get_model_name_from_path
# from search.flash_vstream1.model.builder import load_pretrained_model
from service.search.vstream.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN
from service.search.vstream.conversation import conv_templates, SeparatorStyle
from service.search.vstream.mm_utils import get_model_name_from_path
from service.search.vstream.mm_utils import tokenizer_image_token, KeywordsStoppingCriteria
from service.search.vstream.model.builder import load_pretrained_model

logger = logging.get_logger()


def init_llm_model(args):
    model_name = get_model_name_from_path(args.model_path)
    tokenizer, model, image_processor, context_len = load_pretrained_model(
        args.model_path, args.model_base,
        model_name, args.load_8bit,
        args.load_4bit, device=args.device_llm)

    # model.save_pretrained("/data/yjx/code/Flash-VStream/model/llm_model") # 保存模型

    model.use_video_streaming_mode = True
    if args.video_max_frames is not None:
        model.config.video_max_frames = args.video_max_frames
        logger.info(f'Important: set model.config.video_max_frames = {model.config.video_max_frames}')

    logger.info("search model.device is {}".format(model.device))
    logger.info(model)
    model_kwargs = {
        "model_name": model_name,
        "model": model,
        "tokenizer": tokenizer,
        "processor": image_processor,
    }
    return model_kwargs


llm_model_inited_kwargs = {}


class QwenSearchService:
    def __init__(self, config_dict, args, **kwargs):
        global llm_model_inited_kwargs
        if not llm_model_inited_kwargs:
            llm_model_inited_kwargs = init_llm_model(args)
        self.model_kwargs = llm_model_inited_kwargs
        self.ug_client = UgClient()
        self.meta_engine_url = config_dict.get("meta_engine").get("url")

    def get_answer(self, args, question, llm_frame_queue, vector_faiss, vector_model):
        try:
            logger.info("question={}".format(question))
            text_recall_ans = text_recall(self.meta_engine_url, question)
            caption_results = [index_data["start_time"] + " " + index_data["caption"]
                               for index_data in text_recall_ans["data"]]
            ug_recall_results = self.ug_client.search(question)
            ug_res_str = "\n".join(ug_recall_results)

            help_inf = (
                    f"问题:{question}\n 请根据输入的图像和文本提示，从以下提示信息中筛选出与问题相关的线索，并据此进行推理作答。请注意：并非所有信息都是有用的，需结合上下文判断哪些内容具有实际价值。" + "\n".join(
                caption_results) + ug_res_str)
            vector_results = self.vector_search(args, question, vector_faiss, vector_model)
            text_response = self.search(args, help_inf, llm_frame_queue, vector_results)
            img_response = parse_img(text_recall_ans)
            return text_response, img_response, caption_results, ug_recall_results
        except Exception:
            logger.error(traceback.format_exc())

    def vector_search(self, args, question, vector_faiss, vector_model, top_k=5):
        with torch.inference_mode():
            question_id = clip.tokenize(question).to(args.device_vision)
            question_features = vector_model.encode_text(question_id)
            question_features /= question_features.norm(dim=-1, keepdim=True)
            question_features = question_features.detach().cpu().numpy()
        distances, indices = vector_faiss.search(question_features, top_k)
        indices = [x for x in list(indices[0]) if x != -1]
        result_paths = [os.path.join(args.vision_cache_path, f"{i}.png") for i in indices]
        return result_paths

    def search(self, args, question, llm_frame_queue, vector_results):
        model_name = self.model_kwargs.get("model_name")
        model = self.model_kwargs.get("model")
        tokenizer = self.model_kwargs.get("tokenizer")
        processor = self.model_kwargs.get("processor")

        if 'vstream' in model_name.lower():

            logger.info(f'Using conv_mode={args.conv_mode}')
            conv = conv_templates[args.conv_mode].copy()
            if "mpt" in model_name.lower():
                roles = ('user', 'assistant')
            else:
                roles = conv.roles
            image_tensor = None

            # start QA server
            start_time = datetime.now()
            conv_cnt = 0
            inp = question
            # 获取当前时间
            now = datetime.now()
            conv_start_time = time.perf_counter()
            last_conv_start_time = -1
            # 将当前时间格式化为字符串
            current_time = now.strftime("%H:%M:%S")
            duration = now.timestamp() - start_time.timestamp()

            # 打印当前时间
            print("\nCurrent Time:", current_time, "Run for:", duration)
            logger.info("\nCurrent Time: {} Run for: {}".format(current_time, duration))
            print(f"{roles[0]}: {inp}", end="\n")
            logger.info(f"{roles[0]}: {inp}\n")
            print(f"{roles[1]}: ", end="")
            logger.info(f"{roles[1]}: ")
            # every conversation is a new conversation
            conv = conv_templates[args.conv_mode].copy()
            inp = DEFAULT_IMAGE_TOKEN + '\n' + inp
            conv.append_message(conv.roles[0], inp)

            conv.append_message(conv.roles[1], None)
            prompt = conv.get_prompt()

            input_ids = tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors='pt').unsqueeze(
                0).to(model.device)
            stop_str = conv.sep if conv.sep_style != SeparatorStyle.TWO else conv.sep2
            keywords = [stop_str]
            stopping_criteria = KeywordsStoppingCriteria(keywords, tokenizer, input_ids)
            streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

            llm_start_time = time.perf_counter()
            with torch.inference_mode():
                output_ids = model.generate(
                    input_ids,
                    images=image_tensor,  # image_tensor is None
                    do_sample=True if args.temperature > 0 else False,
                    temperature=args.temperature,
                    max_new_tokens=args.max_new_tokens,
                    streamer=streamer,
                    use_cache=True,
                    stopping_criteria=[stopping_criteria]
                )
            llm_end_time = time.perf_counter()

            outputs = tokenizer.decode(output_ids[0, input_ids.shape[1]:]).strip()
            conv.messages[-1][-1] = outputs
            conv_end_time = time.perf_counter()
            if conv_cnt > 0:
                logger.info(
                    f'CliServer: idx={conv_cnt},\treal_sleep={conv_start_time - last_conv_start_time},\tconv_latency={conv_end_time - conv_start_time},\tllm_latency={llm_end_time - llm_start_time}')
            else:
                logger.info(
                    f'CliServer: idx={conv_cnt},\tconv_latency={conv_end_time - conv_start_time},\tllm_latency={llm_end_time - llm_start_time}')
            conv_cnt += 1
            last_conv_start_time = conv_start_time

        elif any(x in model_name.lower() for x in ["qwen2.5", "qwen2_5", "omni"]):

            messages = [
                {
                    "role": "system",
                    "content": [{"type": "text",
                                 "text": "You are Qwen, a virtual human developed by the Qwen Team, Alibaba Group, capable of perceiving auditory and visual inputs, as well as generating text and speech."}],
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": question}]
                },
            ]
            if llm_frame_queue:
                for frame in llm_frame_queue:
                    messages[1]['content'].append({"type": "image", "image": Image.fromarray(frame[0])})
            for frame in vector_results:
                messages[1]['content'].append({"type": "image", "image": Image.open(frame).convert("RGB")})

            inputs = processor.apply_chat_template(
                messages,
                load_audio_from_video=False,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
                padding=True,
                use_audio_in_video=False
            ).to(model.device)
            streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
            text_ids = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                temperature=args.temperature,
                do_sample=args.temperature > 0,
                eos_token_id=tokenizer.eos_token_id,
                pad_token_id=tokenizer.pad_token_id,
                use_audio_in_video=False,
                streamer=streamer
            )
            outputs = processor.batch_decode(
                text_ids[:, inputs["input_ids"].shape[1]:],
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False
            )[0].strip()

        return outputs


if __name__ == '__main__':

    import argparse
    from decord import VideoReader
    from collections import deque

    from service.process.multimodal.loaders.frame_sampling import uniform_sampling

    parser = argparse.ArgumentParser()
    model_root_path = "/opt/huawei/data2/yjx/projects/Flash-VStream/"
    parser.add_argument("--model-path", type=str, default="/opt/huawei/data1/xxn/Qwen2.5-Omni-7B")
    parser.add_argument("--model-base", type=str, default=None)
    parser.add_argument("--image-file", type=str, default=None)
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
    args = parser.parse_args()

    video_path = "/opt/huawei/data2/atd/code/StreamingQA/data/car/video/test1.mp4"
    video_fps, play_speed = 1.0, 1.0
    llm_frame_queue = deque(maxlen=32)

    vr = VideoReader(video_path)
    video = uniform_sampling(vr, video_fps)
    length = video.shape[0]
    sleep_time = 1 / video_fps / play_speed  # - 计算每帧之间的间隔时间，用于模拟视频的播放速度。
    for start in range(0, length):
        end = min(start + 1, length)
        video_clip = video[start:end]
        llm_frame_queue.append(video_clip)

    input_dict = {"llm_frame_queue": llm_frame_queue}
    search_service = QwenSearchService(args)
    question = "Which parking space is my car parked in?"
    print(search_service.get_answer(args, question, input_dict))
