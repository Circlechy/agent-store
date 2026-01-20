import time
import traceback
from datetime import datetime

import torch
from transformers import TextStreamer

from doc_process.utils import logging
from service.process.multimodal.utils.file_utils import FileStorageWithLock
from service.search.metaengine.handler.recall import text_recall
from service.search.common_search_utils import parse_img
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
    }
    return model_kwargs


llm_model_inited_kwargs = {}


class VstreamSearchService:
    def __init__(self, config_dict, args, **kwargs):
        global llm_model_inited_kwargs
        if not llm_model_inited_kwargs:
            llm_model_inited_kwargs = init_llm_model(args)
        self.model_kwargs = llm_model_inited_kwargs
        self.model_kwargs.get("model").storage = FileStorageWithLock(kwargs.get("embedding_file"))
        self.meta_engine_url = config_dict.get("meta_engine").get("url")

    def get_answer(self, args, question):
        try:
            logger.info("question={}".format(question))
            text_recall_ans = text_recall(self.meta_engine_url, question)
            caption_results = [index_data["start_time"] + " " + index_data["caption"]
                for index_data in text_recall_ans["data"]]

            help_inf = (f"question:{question}\n Here's some information that might help you answer this question:" +
                        "\n".join(
                            caption_results))

            #todo:@hy
            text_response = self.search(args, help_inf)
            img_response = parse_img(text_recall_ans)
            return text_response, img_response
        except Exception:
            logger.error(traceback.format_exc())



    def search(self, args, question):
        model_name = self.model_kwargs.get("model_name")
        model = self.model_kwargs.get("model")
        tokenizer = self.model_kwargs.get("tokenizer")

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
        return outputs
