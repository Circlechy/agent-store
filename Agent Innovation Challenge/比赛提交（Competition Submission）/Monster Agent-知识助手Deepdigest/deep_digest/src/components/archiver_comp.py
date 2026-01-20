"""
归档与清理组件
负责将 LLM 生成的卡片保存到长期记忆，并清理已处理的碎片（熵减）
"""

import uuid
import json
from datetime import datetime
from typing import Any, Dict, List

from openjiuwen.core.component.base import SimpleComponent
from openjiuwen.core.runtime.runtime import Runtime
from src.tools.memory_tools import save_knowledge_cards
from src.tools.inbox_tools import delete_fragments


class ArchiverComponent(SimpleComponent):
    """
    归档组件：保存知识卡片 + 删除源碎片
    
    输入：
        - llm_output: LLM 生成的 JSON 字符串或字典
    
    输出：
        - 统计信息: {"cards_saved": int, "fragments_deleted": int}
    """
    
    def __init__(self):
        super().__init__()
    
    async def invoke(self, inputs, runtime, context) -> Dict[str, Any]:
        """
        执行归档与清理流程
        
        Args:
            inputs: 输入数据字典
            runtime: Workflow runtime context
            context: 上下文对象
        
        Returns:
            统计信息字典
        """
        # 从inputs获取输入数据
        print(f"📦 ArchiverComponent收到inputs类型: {type(inputs)}")
        llm_output = inputs.get("llm_output") if isinstance(inputs, dict) else None
        
        print(f"📦 ArchiverComponent收到llm_output:")
        print(f"   - 类型: {type(llm_output)}")
        if llm_output:
            print(f"   - 值: {str(llm_output)[:200]}...")
        
        if not llm_output:
            result = {"error": "No llm_output provided", "cards_saved": 0, "fragments_deleted": 0}
            return result
        
        # 1. 解析 LLM 输出
        try:
            if isinstance(llm_output, str):
                print(f"🔍 开始解析LLM输出...")
                # 移除可能的 Thought 前缀（新增的日期推理部分）
                clean_output = llm_output.strip()
                
                # 如果有 Thought: 开头，移除该行
                if clean_output.startswith("Thought:"):
                    print(f"✂️ 检测到 Thought 前缀，正在移除...")
                    lines = clean_output.split('\n')
                    clean_output = '\n'.join(lines[1:]).strip()
                    print(f"✂️ 移除 Thought 后的内容 (前100字符): {clean_output[:100]}...")
                
                # 移除markdown代码块标记
                if clean_output.startswith("```json"):
                    print(f"✂️ 移除 ```json 标记")
                    clean_output = clean_output[7:]
                if clean_output.startswith("```"):
                    print(f"✂️ 移除 ``` 标记")
                    clean_output = clean_output[3:]
                if clean_output.endswith("```"):
                    print(f"✂️ 移除末尾 ``` 标记")
                    clean_output = clean_output[:-3]
                clean_output = clean_output.strip()
                
                print(f"📝 清理后的JSON (前200字符): {clean_output[:200]}...")
                print(f"📝 清理后的JSON (最后100字符): ...{clean_output[-100:]}")
                
                data = json.loads(clean_output)
                print(f"✅ JSON解析成功！")
            elif isinstance(llm_output, dict):
                print(f"✅ llm_output已经是字典类型")
                data = llm_output
            else:
                print(f"❌ llm_output类型无效: {type(llm_output)}")
                result = {"error": f"Invalid llm_output type: {type(llm_output)}", "cards_saved": 0, "fragments_deleted": 0}
                return result
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败!")
            print(f"   错误信息: {str(e)}")
            print(f"   错误位置: line {e.lineno}, column {e.colno}")
            print(f"   尝试解析的内容 (前500字符): {clean_output[:500]}...")
            result = {"error": f"JSON decode failed: {str(e)}", "cards_saved": 0, "fragments_deleted": 0}
            return result
        except Exception as e:
            print(f"❌ 解析过程中发生异常: {str(e)}")
            import traceback
            traceback.print_exc()
            result = {"error": f"Parse error: {str(e)}", "cards_saved": 0, "fragments_deleted": 0}
            return result
        
        # 2. 提取卡片列表
        cards = data.get("cards", [])
        if not cards:
            result = {"message": "No cards to save", "cards_saved": 0, "fragments_deleted": 0}
            return result
        
        # 3. 补充缺失字段
        all_fragment_ids = set()  # 收集所有源碎片 ID
        
        for card in cards:
            # 生成 UUID（如果缺失）
            if "id" not in card:
                card["id"] = str(uuid.uuid4())
            
            # 添加时间戳（如果缺失）
            if "created_at" not in card:
                card["created_at"] = datetime.now().isoformat()
            
            # 收集源碎片 ID
            source_ids = card.get("source_fragment_ids", [])
            all_fragment_ids.update(source_ids)
        
        # 4. 保存卡片到长期记忆（原子性保障）
        try:
            save_result = save_knowledge_cards(cards)
            print(f"[ArchiverComponent] {save_result}")
        except Exception as e:
            error_msg = f"Failed to save cards: {str(e)}"
            print(f"❌ [ArchiverComponent] {error_msg}")
            result = {"error": error_msg, "cards_saved": 0, "fragments_deleted": 0}
            return result
        
        # 5. 熵减：删除已处理的碎片（仅在保存成功后执行）
        # 原子性保障：只有当 save_knowledge_cards 成功后，才删除碎片，防止数据丢失
        deleted_count = 0
        if all_fragment_ids:
            try:
                # delete_fragments 返回的是 int（删除的记录数）
                deleted_count = delete_fragments(list(all_fragment_ids))
                print(f"✅ [ArchiverComponent] 熵减清理完成: 删除 {deleted_count} 条碎片")
            except Exception as e:
                # 删除失败不影响整体流程（卡片已保存），但需要警告
                print(f"⚠️ [ArchiverComponent] Warning: Failed to delete fragments: {str(e)}")
                print(f"   - 卡片已保存，但源碎片未删除，需手动清理 IDs: {list(all_fragment_ids)}")
        
        # 6. 返回统计信息
        result = {
            "cards_saved": len(cards),
            "fragments_deleted": deleted_count,
            "message": f"Successfully saved {len(cards)} card(s) and deleted {deleted_count} fragment(s)"
        }
        return result
