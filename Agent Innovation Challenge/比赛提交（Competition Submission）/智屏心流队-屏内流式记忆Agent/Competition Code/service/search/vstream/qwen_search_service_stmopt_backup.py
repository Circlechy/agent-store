import time
import traceback
from datetime import datetime
from PIL import Image
import os
import faiss
import re
import requests
import base64
import io
import json

import torch
from PIL import Image
from transformers import TextStreamer, TextIteratorStreamer
import cn_clip.clip as clip
import torch.nn.functional as F
import threading
from doc_process.utils import logging
from service.process.multimodal.utils.file_utils import FileStorageWithLock
from service.process.multimodal.utils.ug_utils import UgClient
from service.search.common_search_utils import parse_img, parse_vector_img
from service.search.metaengine.handler.recall import text_recall, search
from service.search.vstream.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN
from service.search.vstream.conversation import conv_templates, SeparatorStyle
from service.search.vstream.mm_utils import get_model_name_from_path
from service.search.vstream.mm_utils import tokenizer_image_token, KeywordsStoppingCriteria
from service.search.vstream.model.builder import load_pretrained_model
from openai import OpenAI

logger = logging.get_logger()


def init_llm_model(args):
    model_name = get_model_name_from_path(args.model_path)
    tokenizer, model, image_processor, context_len = load_pretrained_model(
        args.model_path, args.model_base,
        model_name, args.load_8bit,
        args.load_4bit, device=args.device_llm)

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


SYSTEM_PROMPT = """
    <文件内容>：{text_content}
    <用户问题>：{question}

	请根据输入的图像和文本提示<文件内容>，从<文件内容>中筛选出与问题相关的线索，并据此进行推理作答。你的回答必须优先满足"准确答复用户问题"，再考虑"严格隐私保护"。  

    ===【隐私处理工作流程】===
    1. 【敏感信息识别】  
       - 在回答之前，先完整识别<文件内容>中的所有敏感信息。   
       - 敏感信息包括但不限于以下字段：  
         - 宗教信息：十字架，佛像，菩萨，撒旦等
         - 个人身份类：姓名、身份证号、联系方式、车牌号、行驶证号等
         - 位置信息类：家庭住址、公司地址、收件地址等  
         - 医疗健康类：病历、用药记录、体检结果等  
         - 系统密钥类：账号密码、WiFi密码、Token、加密密钥等  
         - 财务数据类：银行卡号、交易流水、收入支出等  
         - 个人偏好类：饮食偏好、运动偏好、其他兴趣爱好等
         - 其他：任何可能导致身份暴露、隐私泄露的信息 

    2. 【披露判断】  
       - 逐条审查 `"敏感信息"`，判断是否有"合理且必要的理由"与<用户问题>直接相关：  
         - 【可披露】：只有在与<用户问题>强相关，且回答用户问题确实需要该信息时，才允许披露。
         - 【不可披露】：无直接必要性时，一律不得披露。  
       - 始终遵循"最小化披露"原则：只提供完成回答所必需的最少信息。 

    3. 【一致性与安全性】  
       - 在“最终回复”部分，严禁直接输出任何【不可披露】的敏感信息。  
       - 如果没有任何可披露内容，则 `"最终回复"` 不得出现任何敏感信息，只能给出基于常规上下文的答复。  
       - 如果<文件内容>无法确定用户问题，直接回答无法确定。

    以JSON格式输出以下内容: 
    {{
        "敏感信息": {{"字段1": ["值1"], "字段2": "值2"}},
        "可披露的敏感信息": {{"字段n": "值n"}},
        "不可披露的敏感信息": {{"字段m": "值m"}},
        "最终回复": "自然语言回答，不得出现“隐私”“敏感信息”“已省略”“无关”等字样。如果信息与问题无关，则在输出中直接忽略。"
    }}
"""

SYSTEM_PROMPT1 = ("""
    <文件内容>：{text_content}
    <用户问题>：{question}
    
	请根据输入的图像和文本提示<文件内容>，从<文件内容>中筛选出与问题相关的线索，并据此进行推理作答。

    以JSON格式输出以下内容：
    "最终回复"：自然语言回答。
    """
)

class QwenSearchService:
    def __init__(self, config_dict, args, **kwargs):
        global llm_model_inited_kwargs
        if not llm_model_inited_kwargs:
            llm_model_inited_kwargs = init_llm_model(args)
        self.model_kwargs = llm_model_inited_kwargs
        self.model_kwargs.get("model").storage = FileStorageWithLock(kwargs.get("embedding_file"))
        self.ug_client = UgClient()
        self.meta_engine_url = config_dict["es_short_term"]["url"]
        self.index_folder = config_dict['faiss_engine']['vision_cache']
        self.total_index_path = os.path.join(self.index_folder, config_dict['faiss_engine']['index'])
        self.index_name = config_dict["es_short_term"]["index"]
        
        # API配置
        self.api_url = 'http://mlops.huawei.com/mlops-service/api/v2/agentService/v1/chat/completions'
        self.api_headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer sk-eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkZXBhcnRtZW50TmFtZSI6IuiwouWwlOW-t-WunumqjOWupCIsImFjY291bnRJZCI6ImQ1OTkwMDQ1NCIsImtleVZlcnNpb24iOiIyLjAiLCJhY2NvdW50TmFtZSI6ImRvbmd5dWt1biIsInRlbmFudElkIjoiMzdmYjY5NTk1ZWUyNjE4YzZlMjk4NjY3MDIxZDI2YTEifQ.5T-lX7g9UhsIjaKS2eY0J66ojZ2A7xsV9HPUkUqkEtY',
        }
        
    def pil_to_base64(self, img):
        """将PIL图像转换为base64编码"""
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    
    def image_path_to_base64(self, image_path):
        """将图像路径转换为base64编码"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
        
    def get_answer(self, args, question, llm_frame_queue, vector_model, prompt_switch):
        try:
            logger.info("question={}".format(question))
            text_recall_ans = search(self.meta_engine_url, self.index_name, question)
            caption_results = [index_data["start_time"] + " " + index_data["caption"]
                               for index_data in text_recall_ans["data"]]
   
            ug_recall_results = self.ug_client.search(question)
            ug_res_str = "\n".join(ug_recall_results)
            if (not ug_recall_results) or (not re.findall(r'"event_id":\s*(\d{11,})', ug_res_str)):
                vector_local_search = False
            else:
                vector_local_search = True
                self.event_id = re.findall(r'"event_id":\s*(\d{11,})', ug_res_str)[0]
                self.vision_cache_folder = os.path.join(self.index_folder, self.event_id)
                self.index_path = os.path.join(self.vision_cache_folder, os.path.basename(self.total_index_path))

            #print("caption result:", "\n".join(caption_results) + ug_res_str)
            help_inf = None
            if prompt_switch:
                help_inf = SYSTEM_PROMPT.format(question=question, text_content="\n".join(caption_results) + ug_res_str)
            else:
                help_inf = SYSTEM_PROMPT1.format(question=question, text_content="\n".join(caption_results) + ug_res_str)

            vector_results = self.vector_search(args, question, vector_local_search, vector_model)
            img_response = parse_img(text_recall_ans) if args.display_img == "text" else parse_vector_img(vector_results)
            yield from self.search(
                args, help_inf, llm_frame_queue, vector_results,
                caption_results, ug_recall_results, img_response
            )
        except Exception:
            logger.error(traceback.format_exc())

    def vector_search(self, args, question, vector_local_search, vector_model, top_k=5):
        faiss_path = self.index_path if vector_local_search and os.path.exists(self.index_path) else self.total_index_path
        assert os.path.exists(faiss_path), f"向量检索路径不存在: {faiss_path}"
        vector_faiss = faiss.read_index(faiss_path)
        with torch.inference_mode():
            question_id = clip.tokenize(question).to(args.device_vision)
            question_features = vector_model.encode_text(question_id)
            question_features /= question_features.norm(dim=-1, keepdim=True)
            question_features = question_features.detach().cpu().numpy()
        distances, indices = vector_faiss.search(question_features, top_k)
        indices = [x for x in list(indices[0]) if x != -1]
        
        if vector_local_search and os.path.exists(self.vision_cache_folder):            
            result_paths = [os.path.join(self.vision_cache_folder, f"{i}.png") for i in indices]
        else:
            all_images = []
            subdirs = sorted([os.path.join(self.index_folder, f) for f in os.listdir(self.index_folder) if os.path.isdir(os.path.join(self.index_folder, f))])
            for folder_path in subdirs:
                images = [f for f in os.listdir(folder_path) if f.endswith(".png")]
                images.sort(key=lambda x: int(os.path.splitext(x)[0]))
                full_paths = [os.path.join(folder_path, img) for img in images]
                all_images.extend(full_paths)
            result_paths = [all_images[i] for i in indices]
        return result_paths

    def search(self, args, question, llm_frame_queue, vector_results,
                  caption_results, ug_recall_results, image_answer):
        model_name = self.model_kwargs.get("model_name")

        if 'vstream' in model_name.lower():
            # vstream模型的处理逻辑保持不变
            model = self.model_kwargs.get("model")
            tokenizer = self.model_kwargs.get("tokenizer")
            processor = self.model_kwargs.get("processor")

            logger.info(f'Using conv_mode={args.conv_mode}')
            conv = conv_templates[args.conv_mode].copy()
            if "mpt" in model_name.lower():
                roles = ('user', 'assistant')
            else:
                roles = conv.roles
            image_tensor = None

            start_time = datetime.now()
            conv_cnt = 0
            inp = question
            now = datetime.now()
            conv_start_time = time.perf_counter()
            last_conv_start_time = -1
            current_time = now.strftime("%H:%M:%S")
            duration = now.timestamp() - start_time.timestamp()

            print("\nCurrent Time:", current_time, "Run for:", duration)
            logger.info("\nCurrent Time: {} Run for: {}".format(current_time, duration))
            print(f"{roles[0]}: {inp}", end="\n")
            logger.info(f"{roles[0]}: {inp}\n")
            print(f"{roles[1]}: ", end="")
            logger.info(f"{roles[1]}: ")
            
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
                    images=image_tensor,
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
            
            yield outputs, image_answer, caption_results, ug_recall_results

        elif any(x in model_name.lower() for x in ["qwen2.5", "qwen2_5", "omni"]):
            # 使用API调用替换本地推理
            messages = [
                {
                    "role": "system",
                    "content": [{"type": "text",
                                 "text": "You are Qwen, a virtual human developed by the Qwen Team, Alibaba Group, capable of perceiving auditory and visual inputs, as well as generating text and speech. You must provide a detailed response."}],
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": question}]
                }
            ]
            
            # 添加实时帧图像
            if llm_frame_queue:
                for frame in llm_frame_queue:
                    img = Image.fromarray(frame[0])
                    image_base64 = self.pil_to_base64(img)
                    messages[1]['content'].append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    })
            
            # 添加向量召回的图像
            for frame_path in vector_results:
                try:
                    image_base64 = self.image_path_to_base64(frame_path)
                    messages[1]['content'].append({
                        "type": "image_url", 
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    })
                except Exception as e:
                    logger.warning(f"Failed to load image {frame_path}: {e}")
                    continue

            # 构造API请求数据
            json_data = {
                "model": "Qwen2.5-VL-72B-Instruct-MLOPS",
                "messages": messages,
                "max_tokens": args.max_new_tokens,
                "temperature": args.temperature,
                # "stream": True  
            }

            try:
                # 发送API请求
                response = requests.post(
                    self.api_url, 
                    headers=self.api_headers, 
                    json=json_data, 
                    proxies={"http": None, "https": None},
                    # stream=True  
                )
                response.raise_for_status()
                # 处理非流式响应
                response_data = response.json()
                content = response_data['choices'][0]['message']['content']
                
                # 解析JSON响应
                # print(content)
                # 处理可能存在的代码块标记
                content = content.strip()
                if content.startswith('```json\n'):
                    content = content[8:]  # 移除开头的```json\n
                if content.startswith('```'):
                    content = content[3:]  # 移除开头的```
                if content.endswith('\n```'):
                    content = content[:-4]  # 移除结尾的\n```
                content = content.strip()
                print(content)
                try:
                    parsed_response = json.loads(content)
                    # 提取key
                    #sensitive_info = parsed_response.get("敏感信息", [])
                    #disclosable_info = parsed_response.get("可披露的敏感信息", [])
                    #non_disclosable_info = parsed_response.get("不可披露的敏感信息", [])
                    final_reply = parsed_response.get("最终回复", "")
                    # 使用解析后的最终回复
                    yield final_reply, image_answer, caption_results, ug_recall_results
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse API response as JSON: {e}")
                    error_msg = f"API调用失败: {str(e)}"
                    yield error_msg, image_answer, caption_results, ug_recall_results

                # partial = ""
                # # 处理流式响应
                # for line in response.iter_lines():
                #     if line:
                #         line = line.decode('utf-8')
                #         if line.startswith('data: '):
                #             try:
                #                 data = line[6:]  # 移除'data: '前缀
                #                 if data.strip() == '[DONE]':
                #                     break
                                    
                #                 chunk_data = json.loads(data)
                #                 if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                #                     delta = chunk_data['choices'][0].get('delta', {})
                #                     content = delta.get('content', '')
                #                     if content:
                #                         partial += content
                #                         yield partial, None, None, None
                #             except json.JSONDecodeError:
                #                 continue
                #             except Exception as e:
                #                 logger.error(f"Error processing streaming response: {e}")
                #                 continue
                
                # # 最终输出包含所有检索结果
                # yield partial, image_answer, caption_results, ug_recall_results
                
            except requests.exceptions.RequestException as e:
                logger.error(f"API request failed: {e}")
                error_msg = f"API调用失败: {str(e)}"
                yield error_msg, image_answer, caption_results, ug_recall_results
            except Exception as e:
                logger.error(f"Unexpected error during API call: {e}")
                error_msg = f"处理过程中出现错误: {str(e)}"
                yield error_msg, image_answer, caption_results, ug_recall_results


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
    sleep_time = 1 / video_fps / play_speed
    for start in range(0, length):
        end = min(start + 1, length)
        video_clip = video[start:end]
        llm_frame_queue.append(video_clip)

    input_dict = {"llm_frame_queue": llm_frame_queue}
    search_service = QwenSearchService(args)
    question = "Which parking space is my car parked in?"
    print(search_service.get_answer(args, question, input_dict))