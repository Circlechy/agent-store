"""Artist节点模块 - 仅保留故事生成逻辑。"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import re

from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.graph.executable import Input, Output
from openjiuwen.core.runtime.runtime import Runtime

from novastar.core.base_node import NovaStarBaseNode
from novastar.utils.multimodal_utils import generate_image, text_to_speech

logger = logging.getLogger(__name__)


class ArtistNode(NovaStarBaseNode):
    """创意Artist节点（仅故事生成）."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化Artist节点.

        Args:
            config: 节点配置
        """
        super().__init__(name="ArtistNode", config=config)
        self._system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """加载系统提示词."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "artist.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return """你是启明星（NovaStar）的创意Agent——Star-Artist。

你是一个充满创意的艺术家，专门为3-12岁的儿童创作故事。

你的能力：
1. 编写温馨有趣的故事
2. 为故事段落生成配图
3. 为故事段落生成语音

你会根据孩子的年龄和兴趣调整创作内容。"""

    def _get_age_group_value(self, age: int) -> str:
        """根据年龄获取年龄组值."""
        if age <= 6:
            return "preschool"
        if age <= 9:
            return "elementary"
        return "upper_elementary"

    async def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        """执行故事生成."""
        query = self.get_input_value(inputs, "query", "")
        user_id = self.get_input_value(inputs, "user_id", "")
        user_context = self.get_input_value(inputs, "context", {})
        age = user_context.get("age", 6)
        interests = user_context.get("interests", [])

        logger.info(f"[ArtistNode] 处理创意请求: query={query[:50]}...")

        idiom = None
        for prefix in ("成语故事：", "成语故事:", "每日成语：", "每日成语:", "成语：", "成语:"):
            if query.startswith(prefix):
                idiom = query[len(prefix):].strip()
                break

        if idiom:
            result = await self._generate_idiom_story(idiom, age)
        else:
            result = await self._generate_story(query, age, interests)

        final_result = {
            "query": query,
            "user_id": user_id,
            "response": result.get("description", "我已经为你准备好了内容！"),
            "content_type": "story",
            "content": result.get("content"),
            "metadata": result.get("metadata", {}),
            "handled_by": "artist",
        }

        logger.info("[ArtistNode] 故事生成完成")
        return final_result

    def _split_text_into_paragraphs(self, text: str, target_paragraphs: int = 5) -> List[str]:
        """将文本分割为段落.

        Args:
            text: 要分割的文本
            target_paragraphs: 目标段落数（1-10）

        Returns:
            段落列表
        """
        # 确保目标段落数在1-10之间
        target_paragraphs = max(1, min(10, target_paragraphs))

        # 先按双换行符分割
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        # 如果段落数少于目标数，尝试按单换行符分割
        if len(paragraphs) < target_paragraphs:
            all_paragraphs = []
            for para in paragraphs:
                sub_paras = [p.strip() for p in para.split("\n") if p.strip()]
                all_paragraphs.extend(sub_paras)
            paragraphs = all_paragraphs

        # 如果段落数仍然不足，按句号、问号、感叹号分割
        if len(paragraphs) < target_paragraphs:
            import re
            all_paragraphs = []
            for para in paragraphs:
                # 按句号、问号、感叹号分割，但保留分隔符
                sentences = re.split(r'([。！？])', para)
                current_sentence = ""
                for i, part in enumerate(sentences):
                    if part in ["。", "！", "？"]:
                        current_sentence += part
                        if current_sentence.strip():
                            all_paragraphs.append(current_sentence.strip())
                        current_sentence = ""
                    else:
                        current_sentence += part
                if current_sentence.strip():
                    all_paragraphs.append(current_sentence.strip())
            paragraphs = all_paragraphs

        # 如果段落数超过目标数，合并相邻段落
        if len(paragraphs) > target_paragraphs:
            # 计算每段应该包含的原始段落数
            segments_per_para = len(paragraphs) / target_paragraphs
            merged_paragraphs = []
            current_segment = []
            segment_count = 0

            for para in paragraphs:
                current_segment.append(para)
                segment_count += 1
                if segment_count >= segments_per_para:
                    merged_paragraphs.append(" ".join(current_segment))
                    current_segment = []
                    segment_count = 0

            if current_segment:
                merged_paragraphs.append(" ".join(current_segment))

            paragraphs = merged_paragraphs

        # 确保段落数在合理范围内，且至少3段
        result = paragraphs[:10] if len(paragraphs) > 10 else paragraphs
        # 如果拆分后少于3段，强制分成3段（按比例分割）
        if len(result) < 3 and len(result) > 0:
            # 将现有段落重新分配为3段
            total_text = ' '.join(result)
            avg_length = len(total_text) // 3
            new_paragraphs = []
            current_pos = 0
            for i in range(3):
                if i == 2:
                    # 最后一段包含剩余所有内容
                    new_paragraphs.append(total_text[current_pos:].strip())
                else:
                    # 尝试在句子边界处分割
                    end_pos = current_pos + avg_length
                    # 向后查找句号、问号、感叹号
                    for j in range(end_pos, min(end_pos + 100, len(total_text))):
                        if total_text[j] in ['。', '！', '？', '.', '!', '?']:
                            end_pos = j + 1
                            break
                    new_paragraphs.append(total_text[current_pos:end_pos].strip())
                    current_pos = end_pos
            result = [p for p in new_paragraphs if p]  # 过滤空段落
        # 如果仍然少于3段，使用备用方案
        if len(result) < 3:
            if len(result) == 1:
                # 单个段落分成3段
                text = result[0]
                text_len = len(text)
                part_len = text_len // 3
                result = [
                    text[:part_len].strip(),
                    text[part_len:2*part_len].strip(),
                    text[2*part_len:].strip()
                ]
            elif len(result) == 2:
                # 两个段落，将第二个段落分成两半
                text = result[1]
                mid = len(text) // 2
                # 在中间位置附近找句号
                for i in range(mid - 20, mid + 20):
                    if i < len(text) and text[i] in ['。', '！', '？', '.', '!', '?']:
                        mid = i + 1
                        break
                result = [
                    result[0],
                    text[:mid].strip(),
                    text[mid:].strip()
                ]
        return result

    async def _split_idiom_story_sections(self, text: str) -> List[str]:
        """按成语故事模板的6个部分拆分文本（保持内容不变）."""
        if not text:
            return []

        plan_prompt = self._build_idiom_story_plan_prompt(text)
        plan_text = await self.chat(
            plan_prompt,
            system_prompt="你是成语故事拆分规划器，只输出JSON，不要输出多余文本。",
        )
        documents = self._parse_idiom_story_plan(plan_text, text)
        if documents:
            return documents
        return self._fallback_idiom_story_sections(text)

    def _build_idiom_story_plan_prompt(self, response: str) -> str:
        """构建成语故事拆分提示词."""
        return (
            "你是“成语故事拆分规划器”。请把下面成语故事拆分为若干段。\n"
            "输出严格JSON：{\"generate\": true, \"documents\": [\"...\", \"...\"]}\n"
            "要求：\n"
            "1) documents 内容从原文中按以下部分拆分（若原文包含该部分就拆）：\n"
            "   - 背景铺垫\n"
            "   - 情节讲述\n"
            "   - 成语由来\n"
            "   - 寓意与应用\n"
            "   - 趣味小延伸\n"
            "   - 结尾鼓励\n"
            "   每个部分对应一个 documents 条目，保留原文内容，不要改写。\n"
            "   第一个 documents 条目必须包含原文开头到第一个部分结束的全部内容；\n"
            "   最后一个 documents 条目必须包含最后一个部分开始到原文结尾的全部内容。\n"
            "2) documents 按原文出现顺序排列。\n"
            "3) 只输出JSON，不要输出多余说明。\n"
            "成语故事：\n"
            f"{response}\n"
        )

    def _parse_idiom_story_plan(self, plan_text: str, response: str) -> List[str]:
        """解析成语故事拆分结果，失败则回退."""
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

        documents = plan.get("documents") if isinstance(plan.get("documents"), list) else []
        documents = [str(doc).strip() for doc in documents if str(doc).strip()]
        if documents:
            return documents
        return []

    def _fallback_idiom_story_sections(self, text: str) -> List[str]:
        """当拆分失败时的简单回退策略."""
        pattern = re.compile(r"(?m)^\s*([1-6])[\.\、]\s*")
        matches = list(pattern.finditer(text))
        if not matches:
            return [text]

        starts = []
        first_start = 0 if matches[0].start() > 0 else matches[0].start()
        starts.append(first_start)
        for match in matches[1:]:
            starts.append(match.start())
            if len(starts) >= 6:
                break

        if len(starts) <= 1:
            return [text]

        sections = []
        for idx, start in enumerate(starts):
            end = starts[idx + 1] if idx + 1 < len(starts) else len(text)
            sections.append(text[start:end])
        return sections

    def _extract_title_and_text(self, content: str) -> Tuple[str, str]:
        """从生成的内容中提取标题和正文.
        
        Args:
            content: 生成的故事内容（第一行是标题，空一行后是正文）
            
        Returns:
            (title, text) 元组，标题和正文
        """
        import re
        
        # 默认值
        default_title = "Novy的奇妙故事"
        default_text = content
        
        # 按行分割
        lines = [line.rstrip() for line in content.split('\n')]
        
        # 找到第一个非空行作为标题
        title = None
        text_start_idx = None
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            # 跳过格式标记行（如 "1) 标题"、"标题："等）
            if re.match(r'^[0-9]+\)\s*标题', line_stripped) or line_stripped == '标题' or line_stripped.startswith('标题：'):
                continue
            
            # 第一行非空且不是格式标记，作为标题
            if title is None:
                # 清理标题中的markdown标记
                title = re.sub(r'\*\*|\*|#+\s*', '', line_stripped).strip()
                # 如果标题太长（超过50字），可能不是标题
                if len(title) > 50:
                    title = None
                    continue
                # 继续找空行后的正文
                continue
            
            # 如果已经找到标题，找到第一个非空行作为正文开始
            if text_start_idx is None:
                text_start_idx = i
                break
        
        # 如果找到了标题和正文起始位置
        if title and text_start_idx is not None:
            text = '\n'.join(lines[text_start_idx:]).strip()
            if text:
                return title, text
        
        # 如果只找到了标题，但没找到明确的正文起始位置
        # 尝试：第一行是标题，第二行是空行，第三行开始是正文
        if len(lines) >= 3:
            first_line = lines[0].strip()
            second_line = lines[1].strip()
            
            # 如果第一行不是格式标记，第二行是空行
            if first_line and not second_line:
                title_candidate = re.sub(r'\*\*|\*|#+\s*', '', first_line).strip()
                if title_candidate and len(title_candidate) <= 50:
                    text = '\n'.join(lines[2:]).strip()
                    if text:
                        return title_candidate, text
        
        # 如果第一行看起来像标题（短且不含格式标记）
        first_line = lines[0].strip() if lines else ""
        if first_line and len(first_line) <= 50:
            if not re.match(r'^[0-9]+\)', first_line) and '标题' not in first_line:
                title_candidate = re.sub(r'\*\*|\*|#+\s*', '', first_line).strip()
                if title_candidate:
                    text = '\n'.join(lines[1:]).strip()
                    # 跳过空行
                    text_lines = [l for l in text.split('\n') if l.strip()]
                    if text_lines:
                        return title_candidate, '\n'.join(text_lines)
        
        # 默认返回
        return default_title, default_text

    def _strip_markdown(self, text: str) -> str:
        """移除常见 Markdown 标记，确保语音仅包含可朗读文本."""
        if not text:
            return ""
        cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
        cleaned = re.sub(r"`{1,3}.*?`{1,3}", "", cleaned, flags=re.S)
        cleaned = re.sub(r"[*#>\-_]+", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    async def _generate_story(
        self, request: str, age: int, interests: List[str], story_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """生成故事（包含文本、图片、语音多模态内容）.

        Args:
            request: 故事请求
            age: 用户年龄
            interests: 用户兴趣

        Returns:
            生成结果，包含段落列表，每个段落包含文本、图片、语音
        """
        age_group_value = self._get_age_group_value(age)
        age_range = "3-6岁" if age <= 6 else ("7-9岁" if age <= 9 else "10-12岁")
        story_length = "1-3分钟" if age <= 6 else "3-5分钟"

        story_prompt = f"""创作一个适合{age_range}儿童的故事。

用户请求：{request}
孩子兴趣：{', '.join(interests[:3]) if interests else '无特定兴趣'}

要求：
1. 长度适中（{story_length}）
2. 温馨、有趣、适合儿童
3. 寓教于乐，传递正向价值观
4. 可以让孩子参与故事发展

输出格式要求（严格按照以下格式，不要添加任何标记或说明）：
第一行：故事标题（简洁有趣，不要加任何标记符号）
第二行：空行
第三行开始：故事正文（必须分为至少3个自然段落，每段2-4句话。段落之间用空行分隔）

重要：故事正文必须包含至少3个段落，每个段落之间用空行分隔。

示例格式：
小兔波波找星星

从前，有一只小兔子叫波波，它住在森林里。

有一天，波波决定去探险，它跳啊跳，来到了一个神奇的花园。

花园里开满了五颜六色的花朵，还有一只友好的蝴蝶在飞舞。"""

        try:
            story_content = await self.chat(story_prompt, system_prompt=self._system_prompt)
        except Exception as e:
            logger.error(f"[ArtistNode] 故事生成失败: {e}")
            story_content = f"""Novy的奇妙故事

从前有一个叫Novy的小伙伴，它非常喜欢探索新世界..."""

        # 从生成的内容中提取标题和正文
        title, story_text = self._extract_title_and_text(story_content)
        
        # 根据文本长度确定段落数（至少3段，最多10段）
        text_length = len(story_text)
        # 文本长度在0-300字：3段，300-600字：3-4段，600-1000字：4-6段，1000+字：6-10段
        if text_length < 300:
            target_paragraphs = 3  # 即使文本很短，也至少分成3段
        elif text_length < 600:
            target_paragraphs = max(3, min(4, text_length // 150))
        elif text_length < 1000:
            target_paragraphs = max(4, min(6, text_length // 200))
        else:
            target_paragraphs = max(6, min(10, text_length // 250))
        
        # 确保至少3段
        target_paragraphs = max(3, target_paragraphs)

        # 分割文本为段落
        paragraphs = self._split_text_into_paragraphs(story_text, target_paragraphs)

        # 为每个段落生成图片和语音
        llm = self.get_llm()
        image_style = "picture_book"  # 故事使用绘本风格

        story_paragraphs = []
        for idx, para_text in enumerate(paragraphs, 1):
            # 为段落生成图片提示词（简化段落内容作为图片描述）
            # 取段落的前100字作为图片描述，如果太短则使用完整段落
            image_prompt = para_text[:100] if len(para_text) > 100 else para_text
            if len(image_prompt) < 10:
                image_prompt = f"{request}，第{idx}段场景"

            # 异步生成图片和语音
            try:
                image_url = await generate_image(
                    llm=llm,
                    prompt=image_prompt,
                    style=image_style,
                    width=1024,
                    height=1024,
                )
            except Exception as e:
                logger.error(f"[ArtistNode] 段落{idx}图片生成失败: {e}")
                image_url = f"[模拟图片URL] paragraph_{idx}"

            try:
                # text_to_speech 现在返回 base64 data URI 格式（data:audio/mp3;base64,{base64}）
                # 可以直接在浏览器中使用，无需额外下载
                audio_data = await text_to_speech(
                    llm=llm,
                    text=para_text,
                    voice="Cherry",
                    age=age,
                )
            except Exception as e:
                logger.error(f"[ArtistNode] 段落{idx}语音生成失败: {e}")
                audio_data = f"[模拟音频] paragraph_{idx}"

            story_paragraphs.append({
                "index": idx,
                "text": para_text,
                "image": image_url,
                "audio": audio_data,  # base64 data URI 格式，可直接在浏览器播放
            })

        return {
            "content": {
                "title": title,
                "text": story_text,  # 保留完整文本（不含标题）
                "paragraphs": story_paragraphs,  # 段落列表，每个段落包含文本、图片、语音
            },
            "description": "我已经为你准备了一个精彩的故事！",
            "metadata": {
                "age_group": age_group_value,
                "duration_minutes": 2 if age <= 6 else 4,  # 3-6岁：1-3分钟（平均2分钟），6-12岁：3-5分钟（平均4分钟）
                "paragraph_count": len(story_paragraphs),
            },
        }

    async def _generate_idiom_story(self, idiom: str, age: int) -> Dict[str, Any]:
        """生成成语故事（面向3-12岁儿童）.

        Args:
            idiom: 成语
            age: 用户年龄

        Returns:
            生成结果，包含内容与说明
        """
        age_group_value = self._get_age_group_value(age)

        prompt_path = Path(__file__).parent.parent / "prompts" / "idiom_story.txt"
        if prompt_path.exists():
            idiom_prompt = prompt_path.read_text(encoding="utf-8")
        else:
            idiom_prompt = ""
        idiom_prompt = idiom_prompt.format(idiom=idiom)

        try:
            story_content = await self.chat(idiom_prompt, system_prompt=self._system_prompt)
        except Exception as e:
            logger.error(f"[ArtistNode] 成语故事生成失败: {e}")
            story_content = f"成语【{idiom}】的故事暂时没生成成功，我们一起再试一次吧！"

        paragraphs = await self._split_idiom_story_sections(story_content)
        llm = self.get_llm()
        image_style = "picture_book"

        story_paragraphs = []
        for idx, para_text in enumerate(paragraphs, 1):
            image_prompt = para_text

            try:
                image_url = await generate_image(
                    llm=llm,
                    prompt=image_prompt,
                    style=image_style,
                    width=512,
                    height=512,
                )
            except Exception as e:
                logger.error(f"[ArtistNode] 成语段落{idx}图片生成失败: {e}")
                image_url = f"[模拟图片URL] idiom_paragraph_{idx}"

            try:
                audio_data = await text_to_speech(
                    llm=llm,
                    text=self._strip_markdown(para_text)[:500],
                    voice="Cherry",
                    age=age,
                )
            except Exception as e:
                logger.error(f"[ArtistNode] 成语段落{idx}语音生成失败: {e}")
                audio_data = f"[模拟音频] idiom_paragraph_{idx}"

            story_paragraphs.append({
                "index": idx,
                "text": para_text,
                "image": image_url,
                "audio": audio_data,
            })

        return {
            "content": {
                "title": f"{idiom}的成语故事",
                "text": story_content,
                "paragraphs": story_paragraphs,
            },
            "description": "我已经为你准备了一个有趣的成语故事！",
            "metadata": {
                "age_group": age_group_value,
                "idiom": idiom,
                "paragraph_count": len(story_paragraphs),
            },
        }

    async def stream_response(
        self, query: str, user_id: str, user_context: Dict[str, Any], intent: Optional[str] = None
    ):
        """流式生成故事内容."""
        age = user_context.get("age", 6)
        interests = user_context.get("interests", [])
        story_length = "1-3分钟" if age <= 6 else "3-5分钟"
        age_range = "3-6岁" if age <= 6 else ("7-9岁" if age <= 9 else "10-12岁")

        story_prompt = f"""创作一个适合{age_range}儿童的故事。

用户请求：{query}
孩子兴趣：{', '.join(interests[:3]) if interests else '无特定兴趣'}

要求：
1. 长度适中（{story_length}）
2. 温馨、有趣、适合儿童
3. 寓教于乐，传递正向价值观
4. 可以让孩子参与故事发展

请直接输出故事内容。"""

        yield {
            "query": query,
            "user_id": user_id,
            "intent": intent or "story",
            "handled_by": "artist",
            "agents": ["artist"],
        }

        story_content = ""
        async for chunk in self.stream_chat(story_prompt, system_prompt=self._system_prompt):
            if chunk:
                story_content += chunk
                yield {"response": chunk}

        if not story_content:
            return

        result = await self._generate_story(query, age, interests, story_content=story_content)
        yield {
            "content": result.get("content", story_content),
            "metadata": result.get("metadata", {}),
            "content_type": "story",
        }
