"""Mentor节点模块 - 基于openjiuwen的智教Agent节点.

仅负责汉字学习与十万个为什么问答。
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.graph.executable import Input, Output
from openjiuwen.core.runtime.runtime import Runtime

from novastar.core.base_node import NovaStarBaseNode
from novastar.utils.multimodal_utils import generate_image, text_to_speech

logger = logging.getLogger(__name__)


class MentorNode(NovaStarBaseNode):
    """智教Mentor节点.

    提供两种能力：
    1. 汉字学习（字形、字音、字义、字源、字网）
    2. 十万个为什么（回答儿童问题）
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化Mentor节点.

        Args:
            config: 节点配置
        """
        super().__init__(name="MentorNode", config=config)
        self._system_prompt = self._load_system_prompt()
        self._character_prompt = self._load_character_prompt()

    def _load_system_prompt(self) -> str:
        """加载系统提示词."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "mentor.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return """你是启明星（NovaStar）的智教Agent——Star-Mentor。

你只负责语言学习：
1. 汉字学习（字形、字音、字义、字源、字网）

请用儿童友好的方式教学。"""

    def _load_character_prompt(self) -> str:
        """加载汉字教学提示词模板."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "mentor_character.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return ""

    async def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        """执行语言学习处理逻辑."""
        query = self.get_input_value(inputs, "query", "")
        user_id = self.get_input_value(inputs, "user_id", "")
        user_context = self.get_input_value(inputs, "context", {})
        age = user_context.get("age", 6)

        lesson_type = self._detect_lesson_type(query, user_context)
        character = await self._extract_character(query)
        lesson = await self.teach_character(character, age)

        response_text = lesson.get("teaching_content", "")
        res = await self._generate_media_from_response(response_text, age)
        result = {
            "query": query,
            "user_id": user_id,
            "content": response_text,
            "response": res,
            "lesson_type": lesson_type,
            "lesson": lesson,
            "handled_by": "mentor",
        }

        logger.info("[MentorNode] 完成语言学习: type=%s", lesson_type)
        return result

    def _detect_lesson_type(self, message: str, context: Dict[str, Any]) -> str:
        """检测语言学习类型."""
        preferred = context.get("language")
        if preferred == "chinese":
            return "chinese"

        message_lower = message.lower()
        if any(word in message for word in ["汉字", "拼音", "笔画", "部首"]):
            return "chinese"
        return "chinese"

    async def _extract_character(self, message: str) -> str:
        """提取要学习的汉字（使用大模型解析）."""
        cleaned = message.strip()
        if not cleaned:
            return "人"
        # 如果本身就是单个汉字，直接返回
        if len(cleaned) == 1 and "\u4e00" <= cleaned <= "\u9fff":
            return cleaned

        prompt = (
            "你是汉字学习助手，请从用户输入中提取要学习的“一个汉字”。\n"
            "要求：\n"
            "1) 只输出一个汉字，不要输出其他文字、标点或解释。\n"
            "2) 如果输入包含多个汉字词组，选最核心/最明确被提及要学习的那个字。\n"
            "3) 如果无法判断，请输出“人”。\n"
            f"用户输入：{cleaned}\n"
            "输出："
        )

        try:
            response = await self.chat(prompt, system_prompt="你只输出一个汉字，不要输出任何其他内容。")
            if response:
                for char in response.strip():
                    if "\u4e00" <= char <= "\u9fff":
                        return char
        except Exception as e:
            logger.error("[MentorNode] 解析汉字失败: %s", e)

        # 回退：从原始输入中取第一个汉字
        for char in cleaned:
            if "\u4e00" <= char <= "\u9fff":
                return char
        return "人"

    def _is_qa_question(self, message: str) -> bool:
        """检测是否是"十万个为什么"类的问题."""
        qa_keywords = [
            "为什么", "怎么", "如何", "是什么", "什么是", "为什么", 
            "为什么是", "为什么会", "为什么会", "为什么有",
            "who", "what", "where", "when", "why", "how"
        ]
        message_lower = message.lower()
        # 检查是否包含问题关键词
        has_qa_keyword = any(keyword in message for keyword in qa_keywords)
        # 检查是否以问号结尾
        has_question_mark = message.strip().endswith("?") or message.strip().endswith("？")
        # 检查是否是疑问句（包含"吗"、"呢"等）
        has_question_word = any(word in message for word in ["吗", "呢", "么"])
        
        return has_qa_keyword or has_question_mark or has_question_word

    async def teach_character(self, character: str, age: int = 6) -> Dict[str, Any]:
        """汉字立体学习模式."""
        teaching_prompt = self._character_prompt.format(character=character, age=age)

        try:
            response = await self.chat(teaching_prompt, system_prompt=self._system_prompt)
            return {
                "lesson_type": "chinese",
                "character": character,
                "teaching_content": response,
            }
        except Exception as e:
            logger.error("[MentorNode] 汉字教学失败: %s", e)
            return {
                "lesson_type": "chinese",
                "character": character,
                "teaching_content": f"让我们一起来学习汉字“{character}”！",
            }

    async def answer_question(self, question: str, age: int = 6) -> Dict[str, Any]:
        """十万个为什么：回答儿童问题.
        
        Args:
            question: 问题内容
            age: 用户年龄
            
        Returns:
            回答结果，包含answer_content、image、audio等字段
        """
        qa_prompt = self._build_qa_prompt(question, age)
        
        try:
            answer_text = await self.chat(qa_prompt, system_prompt=self._system_prompt)
        except Exception as e:
            logger.error("[MentorNode] 问答失败: %s", e)
            answer_text = f"这是一个很有趣的问题！让我来告诉你答案。"
        
        # 判断是否需要生成图片和语音
        need_media = await self._should_generate_media_for_qa(answer_text, question, age)
        
        result = {
            "lesson_type": "qa",
            "question": question,
            "answer_content": answer_text,
            "image": "",
            "audio": "",
        }
        
        # 如果需要生成多媒体内容
        if need_media.get("generate", False):
            llm = self.get_llm()
            
            # 生成图片（如果需要）
            if need_media.get("need_image", False):
                image_prompt = need_media.get("image_prompt", answer_text[:100])
                try:
                    image_url = await generate_image(
                        llm=llm,
                        prompt=image_prompt,
                        style="picture_book",
                        width=1024,
                        height=1024,
                    )
                    result["image"] = image_url
                    logger.info("[MentorNode] 问答配图生成成功")
                except Exception as e:
                    logger.error("[MentorNode] 问答配图生成失败: %s", e)
            
            # 生成语音（如果需要）
            if need_media.get("need_audio", True):  # 默认生成语音
                try:
                    audio_data = await text_to_speech(
                        llm=llm,
                        text=self._strip_markdown(answer_text),
                        voice="Cherry",
                        age=age,
                    )
                    result["audio"] = audio_data
                    logger.info("[MentorNode] 问答语音生成成功")
                except Exception as e:
                    logger.error("[MentorNode] 问答语音生成失败: %s", e)
        
        return result

    def _build_qa_prompt(self, question: str, age: int) -> str:
        """构建"十万个为什么"问题的提示词."""
        age_range = "3-6岁" if age <= 6 else ("7-9岁" if age <= 9 else "10-12岁")
        
        prompt = f"""请回答一个{age_range}儿童的问题。

问题：{question}

要求：
1. 用孩子能理解的语言解释
2. 内容简洁有趣（2-3句话）
3. 可以适当使用比喻和例子
4. 激发孩子的好奇心，可以提出一个小问题引导思考

请直接给出答案，不要添加"问题："、"答案："等标记。"""
        return prompt

    async def _should_generate_media_for_qa(
        self, answer_text: str, question: str, age: int
    ) -> Dict[str, Any]:
        """判断问答内容是否需要生成图片和语音.
        
        Args:
            answer_text: 生成的答案文本
            question: 原始问题
            age: 用户年龄
            
        Returns:
            包含generate、need_image、need_audio、image_prompt等字段的字典
        """
        media_judge_prompt = self._build_media_judge_prompt(answer_text, question, age)
        
        try:
            judge_result = await self.chat(
                media_judge_prompt,
                system_prompt="你是多媒体内容规划器，只输出JSON，不要输出多余文本。",
            )
            plan = self._parse_media_judge_result(judge_result)
            
            # 默认需要生成语音
            if plan.get("generate", False):
                return {
                    "generate": True,
                    "need_image": plan.get("need_image", False),
                    "need_audio": plan.get("need_audio", True),
                    "image_prompt": plan.get("image_prompt", answer_text[:100]),
                }
            else:
                # 即使不需要图片，也默认生成语音
                return {
                    "generate": True,
                    "need_image": False,
                    "need_audio": True,
                    "image_prompt": "",
                }
        except Exception as e:
            logger.error("[MentorNode] 多媒体判断失败: %s", e)
            # 默认生成语音，不生成图片
            return {
                "generate": True,
                "need_image": False,
                "need_audio": True,
                "image_prompt": "",
            }

    def _build_media_judge_prompt(self, answer_text: str, question: str, age: int) -> str:
        """构建多媒体内容判断提示词."""
        age_range = "3-6岁" if age <= 6 else ("7-9岁" if age <= 9 else "10-12岁")
        
        prompt = f"""请判断以下{age_range}儿童的问答内容是否需要生成图片和语音。

问题：{question}
答案：{answer_text}

请判断：
1. 是否需要生成图片：如果答案中包含可画面表达的内容（如自然现象、动物、物体、场景等），则生成图片
2. 是否需要生成语音：通常需要，除非答案太短（少于10字）

输出严格JSON格式：
{{
    "generate": true/false,
    "need_image": true/false,
    "need_audio": true/false,
    "image_prompt": "如果需要图片，提供图片生成提示词（简洁，20字以内）"
}}

示例：
- 如果答案描述天空、动物等可见内容：{{"generate": true, "need_image": true, "need_audio": true, "image_prompt": "蓝色的天空和白云"}}
- 如果答案只是抽象概念：{{"generate": true, "need_image": false, "need_audio": true, "image_prompt": ""}}"""
        return prompt

    def _parse_media_judge_result(self, judge_text: str) -> Dict[str, Any]:
        """解析多媒体判断结果."""
        plan = {}
        try:
            plan = json.loads(judge_text)
        except json.JSONDecodeError:
            # 尝试提取JSON
            match = re.search(r"\{.*\}", judge_text, re.S)
            if match:
                try:
                    plan = json.loads(match.group(0))
                except json.JSONDecodeError:
                    plan = {}
        
        return {
            "generate": bool(plan.get("generate", True)),
            "need_image": bool(plan.get("need_image", False)),
            "need_audio": bool(plan.get("need_audio", True)),
            "image_prompt": str(plan.get("image_prompt", "")).strip(),
        }

    async def _generate_media_from_response(self, response: str, age: int) -> List[Dict[str, str]]:
        """根据教学内容生成配图与语音.

        Returns:
            [{"image": "...", "text": "...", "audio": "..."}, ...]
        """
        cleaned = response.strip()
        if not cleaned:
            return []

        plan_prompt = self._build_image_plan_prompt(cleaned)
        plan_text = await self.chat(
            plan_prompt,
            system_prompt="你是配图规划器，只输出JSON，不要输出多余文本。",
        )
        generate, documents = self._parse_image_plan(plan_text, cleaned)
        if not generate or not documents:
            audio_data = ""
            try:
                audio_data = await text_to_speech(
                    llm=self.get_llm(),
                    text=self._strip_markdown(response)[:500],
                    voice="Cherry",
                    age=age,
                )
            except Exception as e:
                logger.error("[MentorNode] 文本转语音失败: %s", e)
            return [{"image": "", "text": response, "audio": audio_data}]

        llm = self.get_llm()

        res = []
        for doc in documents:
            try:
                image_url = await generate_image(
                    llm=llm,
                    prompt=doc,
                    style="picture_book",
                    width=512,
                    height=512,
                )
            except Exception as e:
                logger.error("[MentorNode] 图片生成失败: %s", e)
                image_url = ""

            try:
                audio_data = await text_to_speech(
                    llm=llm,
                    text=self._strip_markdown(doc),
                    voice="Cherry",
                    age=age,
                )
            except Exception as e:
                logger.error("[MentorNode] 文本转语音失败: %s", e)
                audio_data = ""
            res.append({"image": image_url, "text": doc, "audio": audio_data})
        return res

    def _build_image_plan_prompt(self, response: str) -> str:
        """构建配图规划提示词."""
        return (
            "你是“教学内容配图规划器”。请判断下面教学内容是否需要配图。\n"
            "如果不需要，输出严格JSON：{\"generate\": false, \"documents\": []}\n"
            "如果需要，输出严格JSON：{\"generate\": true, \"documents\": [\"...\", \"...\"]}\n"
            "要求：\n"
            "1) 仅当内容包含可画面表达的场景/形象/字形结构/例句场景时才生成。\n"
            "2) documents 内容从原文中按以下部分拆分（若原文包含该部分就拆）：\n"
            "   - 汉字起源\n"
            "   - 演变过程\n"
            "   - 字形拆解\n"
            "   - 生活联想\n"
            "   - 组词造句\n"
            "   - 小技巧提示\n"
            "   - 趣味小故事\n"
            "   每个部分对应一个 documents 条目，保留原文内容，不要改写。\n"
            "   第一个 documents 条目必须包含原文开头到第一个部分结束的全部内容；\n"
            "   最后一个 documents 条目必须包含最后一个部分开始到原文结尾的全部内容。\n"
            "3) documents 按原文出现顺序排列。\n"
            "4) 只输出JSON，不要输出多余说明。\n"
            "教学内容：\n"
            f"{response}\n"
        )

    def _parse_image_plan(self, plan_text: str, response: str) -> Tuple[bool, List[str]]:
        """解析配图规划结果，失败则使用回退策略."""
        plan = {}
        try:
            plan = json.loads(plan_text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", plan_text, re.S)
            if match:
                try:
                    plan = json.loads(match.group(0))
                except json.JSONDecodeError:
                    plan = {}

        generate = bool(plan.get("generate"))
        documents = plan.get("documents") if isinstance(plan.get("documents"), list) else []
        documents = [str(doc).strip() for doc in documents if str(doc).strip()]
        if generate and documents:
            return True, documents

        fallback_docs = self._fallback_image_documents(response)
        if fallback_docs:
            return True, fallback_docs
        return False, []

    def _fallback_image_documents(self, response: str) -> List[str]:
        """当规划解析失败时的简单切分策略."""
        paragraphs = [p.strip() for p in response.splitlines() if p.strip()]
        if not paragraphs:
            return []
        return paragraphs

    def _strip_markdown(self, text: str) -> str:
        """移除常见 Markdown 标记，仅保留可朗读文本."""
        if not text:
            return ""
        cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
        cleaned = re.sub(r"`{1,3}.*?`{1,3}", "", cleaned, flags=re.S)
        cleaned = re.sub(r"[*#>\-_]+", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    async def stream_response(
        self, query: str, user_id: str, user_context: Dict[str, Any], intent: Optional[str] = None
    ):
        """流式生成问答内容."""
        age = user_context.get("age", 6)
        
        # 判断是否是问答意图
        if intent == "qa" or self._is_qa_question(query):
            # 流式生成答案文本
            qa_prompt = self._build_qa_prompt(query, age)
            
            yield {
                "query": query,
                "user_id": user_id,
                "intent": "qa",
                "handled_by": "mentor",
                "agents": ["mentor"],
            }
            
            answer_text = ""
            async for chunk in self.stream_chat(qa_prompt, system_prompt=self._system_prompt):
                if chunk:
                    answer_text += chunk
                    yield {"response": chunk}
            
            if not answer_text:
                return
            
            # 基于已生成的文本，判断并生成图片和语音
            need_media = await self._should_generate_media_for_qa(answer_text, query, age)
            
            result_content = {
                "question": query,
                "answer_content": answer_text,
                "image": "",
                "audio": "",
            }
            
            # 如果需要生成多媒体内容
            if need_media.get("generate", False):
                llm = self.get_llm()
                
                # 生成图片（如果需要）
                if need_media.get("need_image", False):
                    image_prompt = need_media.get("image_prompt", answer_text[:100])
                    try:
                        image_url = await generate_image(
                            llm=llm,
                            prompt=image_prompt,
                            style="picture_book",
                            width=1024,
                            height=1024,
                        )
                        result_content["image"] = image_url
                        logger.info("[MentorNode] 问答配图生成成功")
                    except Exception as e:
                        logger.error("[MentorNode] 问答配图生成失败: %s", e)
                
                # 生成语音（如果需要）
                if need_media.get("need_audio", True):  # 默认生成语音
                    try:
                        audio_data = await text_to_speech(
                            llm=llm,
                            text=self._strip_markdown(answer_text),
                            voice="Cherry",
                            age=age,
                        )
                        result_content["audio"] = audio_data
                        logger.info("[MentorNode] 问答语音生成成功")
                    except Exception as e:
                        logger.error("[MentorNode] 问答语音生成失败: %s", e)
            
            # 返回完整结果
            yield {
                "content": result_content,
                "content_type": "qa",
                "lesson_type": "qa",
            }
        else:
            # 非问答意图，使用原来的逻辑（语言学习）
            yield {
                "query": query,
                "user_id": user_id,
                "intent": intent or "learning",
                "handled_by": "mentor",
                "agents": ["mentor"],
            }
            
            # 这里可以添加语言学习的流式响应逻辑
            # 暂时返回空，让 workflow 使用 _do_invoke
            return
