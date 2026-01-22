# import time
# import traceback
# from datetime import datetime
# from pathlib import Path
# from typing import List, Dict
#
# import torch
# from transformers import TextStreamer
#
# from doc_process.utils import logging
# from service.process.multimodal.qwen.utils import TextSearch, VideoUtils
# from service.process.multimodal.qwen_process_service import vision_model_inited_kwargs
# from service.process.multimodal.utils.file_utils import FileStorageWithLock
# from service.search.metaengine.handler.recall import text_recall
# # from search.flash_vstream1.mm_utils import get_model_name_from_path
# # from search.flash_vstream1.model.builder import load_pretrained_model
# from service.search.vstream.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN
# from service.search.vstream.conversation import conv_templates, SeparatorStyle
# from service.search.vstream.mm_utils import get_model_name_from_path
# from service.search.vstream.mm_utils import tokenizer_image_token, KeywordsStoppingCriteria
# from service.search.vstream.model.builder import load_pretrained_model
#
# logger = logging.get_logger()
#
# class QwenSearchService:
#     def __init__(self, **kwargs):
#         self.model_kwargs = vision_model_inited_kwargs
#         self.model = self.model_kwargs.get("model")
#         self.processor=self.model_kwargs.get("processor")
#         self.input_kwargs = kwargs
#         self.MAX_FRAMES = self.input_kwargs.get("MAX_FRAMES")
#     def get_answer(self,  question):
#         try:
#             text_recall_ans = text_recall(question)
#             text_recall_ans = list(set(text_recall_ans))
#
#             return self.answer_query(question,text_recall_ans)
#         except Exception:
#             logger.error(traceback.format_exc())
#
#     # ─── 2. 在 answer_query() 中插入 clip ─────────────────────
#     def answer_query(self,query: str, schemas: List[Dict]):
#         caps = [s["caption"] for s in schemas]
#         vect, mat = TextSearch.build_tfidf(caps)
#         idx  = TextSearch.most_similar(query, vect, mat)
#         best = schemas[idx]
#         # print('index:', index)
#
#         tmp_clip = VideoUtils.build_clip_mp4(best)                       # 生成 64 帧 mp4 临时文件
#
#         # ========== 新写法：用 messages 结构 ==========
#         messages = [
#             {"role": "system",
#              "content":[{"type":"text","text":"You are Qwen-Omni, a helpful video assistant."}]},
#             {"role": "user",
#              "content":[
#                 {"type":"video","video": str(tmp_clip), "max_frames": self.MAX_FRAMES},
#                 {"type":"text", "text": f"场景摘要：{best['caption']}\\n\\n问题：{query}"}
#              ]}
#         ]
#
#         text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
#         audio_in, img_in, vid_in = process_mm_info(messages, use_audio_in_video=False)
#         inputs = self.processor(text=text,
#                            images=img_in,
#                            videos=vid_in,
#                            audio=None,
#                            padding=True,
#                            return_tensors="pt").to(self.model.device)
#
#         with torch.no_grad():
#             out = self.model.generate(**inputs, max_new_tokens=128, return_audio=False)
#
#         tmp_clip.unlink()                                     # 删除临时文件
#         ans_ids = out[0][inputs.input_ids.shape[1]:]
#         return self.processor.decode(ans_ids, skip_special_tokens=True)