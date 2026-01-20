"""
Brain Component - 自定义LLM调用组件
绕过LLMComponent的限制，直接调用LLM API
"""

import json
from openjiuwen.core.component.base import SimpleComponent
from openjiuwen.core.runtime.base import Runtime


class BrainComponent(SimpleComponent):
    """
    Brain组件 - 执行知识蒸馏的LLM调用
    
    直接使用OpenAI客户端调用LLM，避免框架的LLMComponent限制
    """
    
    def __init__(self, model_config, system_prompt: str):
        """
        初始化Brain组件
        
        Args:
            model_config: 模型配置对象
            system_prompt: 系统提示词
        """
        super().__init__()
        self.model_config = model_config
        self.system_prompt = system_prompt
    
    async def invoke(self, inputs, runtime, context):
        """
        执行LLM调用进行知识蒸馏
        
        Args:
            inputs: 输入数据
            runtime: 运行时上下文
            context: 上下文对象
        
        Returns:
            dict: {"cards": "JSON字符串"}
        """
        try:
            # 1. 获取输入
            fragments = inputs.get("fragments", "[]") if isinstance(inputs, dict) else "[]"
            memory_index = inputs.get("memory_index", "[]") if isinstance(inputs, dict) else "[]"
            
            # 2. 构建消息
            user_message = f"""待处理碎片：
{fragments}

现有记忆库索引：
{memory_index}

请按照系统提示生成知识卡片的JSON输出。"""
            
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # 3. 直接调用OpenAI API
            from openai import AsyncOpenAI
            
            # 从model_config提取配置
            api_key = self.model_config.model_info.api_key
            api_base = self.model_config.model_info.api_base
            
            # 获取模型名（尝试多种可能的属性名）
            model_name = (
                getattr(self.model_config.model_info, 'model_name', None) or
                getattr(self.model_config.model_info, 'model', None) or
                getattr(self.model_config.model_info, 'name', None)
            )
            
            if not model_name:
                raise ValueError("无法获取模型名称，请检查 config.py 中的 ModelConfig 配置")
            
            print(f"🔗 调用LLM: {model_name}")
            
            # 创建客户端（根据配置决定是否验证SSL）
            import httpx
            client = AsyncOpenAI(
                api_key=api_key,
                base_url=api_base,
                http_client=httpx.AsyncClient(verify=False)
            )
            
            # 调用LLM
            response = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=4000
            )
            
            # 4. 提取响应并返回
            llm_output = response.choices[0].message.content
            print(f"✅ LLM调用成功 (输出长度: {len(llm_output)})")
            
            result = {"cards": llm_output}
            
            return result
            
        except Exception as e:
            print(f"❌ Brain组件执行失败: {e}")
            import traceback
            traceback.print_exc()
            
            # 返回空结果
            result = {"cards": json.dumps({"cards": []}, ensure_ascii=False)}
            return result
