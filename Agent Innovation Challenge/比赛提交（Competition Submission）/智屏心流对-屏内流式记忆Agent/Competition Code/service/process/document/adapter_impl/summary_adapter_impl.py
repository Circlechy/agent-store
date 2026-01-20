#  Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

"""
服务化样例代码，各 adapter 的实现类样例
"""
import os
import re
from abc import abstractmethod

import torch
from transformers import AutoTokenizer, AutoModel, GenerationConfig
from transformers.utils import GENERATION_CONFIG_NAME

from doc_process.processors.base.adapter.summary_adapter import StructureSummaryAdapter
from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from doc_process.utils.error_code import ProcessorException, ErrorCode

logger = logging.get_logger()


class BaseStructureSummaryForSummarization(StructureSummaryAdapter):
    """
    BaseStructureSummaryForSummarization: One implementation of StructureSummaryAdapter. abstract
    """

    def __init__(self, model, tokenizer, prompt, input_keys, max_token):
        self.name = "BaseLLM"
        self.model = model
        self.tokenizer = tokenizer
        self.prompt = prompt
        self.input_keys = input_keys
        self.max_token = max_token

    @abstractmethod
    def _forward(self, **kwargs) -> str:
        raise NotImplementedError()


class ChatGLM3ForSummarization(BaseStructureSummaryForSummarization):
    """
    ChatGLM3ForSummarization: use BaiChuan2 and chosen prompt to generate summaries.
    """

    def __init__(self, name, model, tokenizer, prompt, input_keys, max_token):
        super().__init__(model, tokenizer, prompt, input_keys, max_token)
        self.name = name

        if self.model is None or self.tokenizer is None:
            raise ProcessorException(ErrorCode.VALUE_ERROR, f"Invalid LLM model of {self.name}")

    def _forward(self, **kwargs) -> str:
        self.model.eval()
        missing_keys = set(self.input_keys) - set(kwargs.keys())
        if missing_keys:
            raise ProcessorException(ErrorCode.VALUE_ERROR,
                                     f"Missing keys for updating the variable: {list(missing_keys)}")
        input_kwargs = {k: v for k, v in kwargs.items() if k in self.input_keys}

        user_prompt = self.prompt
        for placeholder in self.input_keys:
            try:
                if isinstance(input_kwargs, dict):
                    value = input_kwargs[placeholder]
                else:
                    value = getattr(input_kwargs, placeholder)
            except Exception as error:
                value = ""
                logger.warning(f"value for placeholder in prompt is invalid, {error}")
            user_prompt = user_prompt.replace("{{" + placeholder + "}}", str(value))

        sys_prompt = "<|system|>你是一位AI助手，主要任务是根据用户输入内容，生成精简、准确、保留核心信息的摘要内容。" \
                     "当用户提供的内容仅包括核心主旨时，你需要尽可能从原文摘抄，并作适当的润色，让摘要内容语句通顺。" \
                     "当用户提供的内容详细阐述了细节而且篇幅较长时，你需要对内容进行概括压缩，提纲挈领。" \
                     "如果用户没有提供具体的文章内容，或者你无法生成摘要，请你直接回答'''抱歉，无法生成摘要'''。"
        user_prompt = "<|user|>{}".format(user_prompt)
        assistant_prompt = "<|assistant|>"
        prompt = "\n".join([sys_prompt, user_prompt, assistant_prompt])
        try:
            response, _ = self.model.chat(
                self.tokenizer, prompt[:self.max_token], history=None, num_beams=1, do_sample=True, top_p=0.8,
                temperature=0.8)
        except Exception as error:
            logger.error(f"LLM chatglm3 generate summary fail, {error}")
            response = ""
        response = re.sub(
            r"(<\|system\|>|<\|user\|>|<\|assistant\|>|<\|observation\|>|<\|end\|>|<摘要内容>|</摘要内容>)",
            "",
            str(response)
        )
        return response


SPECIAL_MODEL_NAMES = {
    "chatglm3": ChatGLM3ForSummarization
}

SPECIAL_MODEL_MAX_TOKEN = {
    "chatglm3": 8192
}

SPECIAL_MODEL_PROMPTS = {
    "structure": "structure_summary.pr"
}


class AutoLLMForSummarization:
    """
    AutoLLMForSummarization: common entrances to initialize StructureSummaryAdapter adapter
    """

    @classmethod
    def from_pretrained(cls, config):
        """
        initialize LLMForSummarization model
        Args:
            config: user config, including:
                pretrained_model_name_or_path: LLM local path
                model_type: model name
                prompt_type: prompt type
                device: cpu or cuda:0
        Return:
            a adapter class instance
        """
        CheckUtils.check_type(config, dict, "config")
        config = config.get("extractor", {})
        if not config.get("is_generated_summary_chunk", False):
            logger.warning("Config extractor.is_generated_summary_chunk=False now, your adapter is disabled.")
            return None
        # 当is_generated_summary_chunk=True时，local_llm_path必填
        pretrained_model_name_or_path = config.get("local_llm_path")
        if pretrained_model_name_or_path is not None and isinstance(
                pretrained_model_name_or_path, str) and os.path.exists(str(pretrained_model_name_or_path)):
            model_type = config.get("model_type", "chatglm3")
            prompt_type = config.get("prompt_type", "structure")
            device = config.get("device", "cuda:0")
        else:
            raise ProcessorException(ErrorCode.VALUE_ERROR, "Invalid LLM extractor.local_llm_path.")

        if model_type not in SPECIAL_MODEL_NAMES:
            raise ProcessorException(ErrorCode.VALUE_ERROR, f"Invalid LLM extractor.model_type of {model_type}")
        model_class = SPECIAL_MODEL_NAMES[model_type]
        if cls.check_device(device):
            device = device.lower()
        else:
            raise ProcessorException(ErrorCode.VALUE_ERROR, f"Param extractor.device {device} is invalid.")
        tokenizer = AutoTokenizer.from_pretrained(pretrained_model_name_or_path, trust_remote_code=True)
        model = AutoModel.from_pretrained(pretrained_model_name_or_path, trust_remote_code=True,
                                          device_map=device).eval()
        config_path = str(os.path.join(pretrained_model_name_or_path, GENERATION_CONFIG_NAME))
        if os.path.exists(config_path):
            model.generation_config = GenerationConfig.from_pretrained(pretrained_model_name_or_path)
        max_token = SPECIAL_MODEL_MAX_TOKEN.get(model_type, 0)
        if prompt_type not in SPECIAL_MODEL_PROMPTS:
            raise ProcessorException(ErrorCode.VALUE_ERROR, f"Invalid LLM extractor.prompt_type of {prompt_type}")
        prompt = cls.load_prompt(prompt_type)

        placeholders = []
        placeholder_matches = re.finditer(r"\{\{(.*?)\}\}", prompt)
        for match in placeholder_matches:
            placeholder = match.group(1).strip()
            if len(placeholder) == 0:
                raise ProcessorException(ErrorCode.VALUE_ERROR, "Prompt Placeholders cannot be empty string.")
            if placeholder not in placeholders:
                placeholders.append(placeholder)
            prompt = prompt.replace(match.group(0), "{{" + placeholder + "}}")
        return model_class(model_type, model, tokenizer, prompt, placeholders, max_token)

    @classmethod
    def load_prompt(cls, prompt_type) -> str:
        """load prompt file from local"""
        prompts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")
        prompt_file = SPECIAL_MODEL_PROMPTS[prompt_type]
        with open(os.path.join(prompts_dir, prompt_file), "r", encoding="utf8") as f:
            template = f.read()
        return template

    @classmethod
    def check_device(cls, device) -> bool:
        """check valid device"""
        if device is None or (not isinstance(device, str)):
            result = False
        elif device.lower() == "cpu":
            result = True
        elif device.lower() != "cpu" and (not torch.cuda.is_available()):
            result = False
        else:
            try:
                device_gpu = int(device.lower().strip("cuda:"))
                result = 0 <= device_gpu < torch.cuda.device_count()
            except ProcessorException(ErrorCode.VALUE_ERROR):
                result = False
        return result
