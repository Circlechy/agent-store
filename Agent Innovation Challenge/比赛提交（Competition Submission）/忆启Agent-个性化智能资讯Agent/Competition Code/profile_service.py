import asyncio
from datetime import datetime
import json
import re
from flask import Flask, request, jsonify
import threading
import time

app = Flask(__name__)

# 导入必要的库和模块
import os
from pathlib import Path
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv


# 加载环境变量
# 获取当前脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))

# 加载环境变量 - 使用绝对路径确保能找到.env文件
env_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=env_path)

# 添加项目根目录到Python路径
script_path = os.path.abspath(__file__)
learning_assistant_path = os.path.dirname(script_path)
examples_path = os.path.dirname(learning_assistant_path)
agent_core_path = os.path.dirname(examples_path)
sys.path.insert(0, agent_core_path)

# 导入 OpenJiuWen 相关模块
from openjiuwen.core.utils.llm.messages import BaseMessage
from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory
from openjiuwen.core.common.logging import logger
from openjiuwen.core.memory.mem_unit.memory_unit import UserProfileUnit, MemoryType
from openjiuwen.core.memory.store.impl.chroma_semantic_store import ChromaSemanticStore
from openjiuwen.core.utils.tool.tool import tool
from openjiuwen.core.memory.engine.memory_engine import MemoryEngine
from openjiuwen.core.memory.store.impl.dbm_kv_store import DbmKVStore
from openjiuwen.core.memory.store.impl.default_db_store import DefaultDbStore
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo
from openjiuwen.core.memory.manage.data_id_manager import DataIdManager
from openjiuwen.core.utils.prompt.template.template import Template
from openjiuwen.agent.react_agent.react_agent import ReActAgent
from openjiuwen.agent.react_agent import create_react_agent_config
from openjiuwen.core.memory.config.config import SysMemConfig
from openjiuwen.core.memory.embed_models.api import APIEmbedModel
from memory_workflow_agent import create_memory_workflow_agent, get_news, filter_news_fields
from openjiuwen.core.memory.manage.data_id_manager import DataIdManager

API_BASE = os.getenv("API_BASE")
API_KEY = os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER")  # 使用小写的openai以匹配model_library中的实现
os.environ["LLM_SSL_VERIFY"] = "False"
os.environ["EMBED_SSL_VERIFY"] = "False"

embed_model = APIEmbedModel(
    base_url=os.getenv("EMBED_API_BASE"),
    model_name=os.getenv("EMBED_MODEL_NAME"),
    api_key=os.getenv("EMBED_API_KEY"),
    timeout=int(os.getenv("EMBED_TIMEOUT")),
    max_retries=int(os.getenv("EMBED_MAX_RETRIES")),
)

# 使用之前定义的项目根目录
# 将 resources 目录放在 Competition Code 目录下
data_id_generator = DataIdManager()
resource_dir = os.path.join(script_dir, 'resources')

# 创建 KV Store
kv_db_path = os.path.join(resource_dir, 'dbmstore.db')
kv_store = DbmKVStore(kv_db_path)

# 创建语义存储
semantic_store = ChromaSemanticStore(resource_dir, embed_model)

# 创建数据库存储
path = Path(f"{resource_dir}/news_sql_db.db").resolve()
db_store = DefaultDbStore(create_async_engine(f"sqlite+aiosqlite:///{path}"))

# 注册存储
MemoryEngine.register_store(kv_store=kv_store, semantic_store=semantic_store, db_store=db_store)

# 全局记忆引擎变量
memory_engine = None
workflow_agent = None
global_loop = None
sys_config = SysMemConfig()

# 用于同步初始化的锁
init_lock = threading.Lock()
is_initialized = False

def start_background_loop():
    """启动后台事件循环线程"""
    global global_loop
    global_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(global_loop)
    global_loop.run_forever()

def run_coroutine_in_global_loop(coro):
    """在全局事件循环中运行协程"""
    global global_loop, loop_thread
    if global_loop is None or global_loop.is_closed():
        # 重新启动事件循环
        global_loop = asyncio.new_event_loop()
        loop_thread = threading.Thread(target=start_background_loop, daemon=True)
        loop_thread.start()
        time.sleep(0.1)  # 给一点时间让循环启动
    
    future = asyncio.run_coroutine_threadsafe(coro, global_loop)
    return future.result(timeout=30)  # 设置超时防止永久等待
# 初始化函数 - 使用线程安全的方式
def init_memory_engine_sync():
    global memory_engine, workflow_agent, embed_model, is_initialized
    
    with init_lock:
        if is_initialized:
            return
        
        # 启动后台事件循环
        global global_loop, loop_thread
        if global_loop is None:
            global_loop = asyncio.new_event_loop()
            loop_thread = threading.Thread(target=start_background_loop, daemon=True)
            loop_thread.start()
            time.sleep(0.1)  # 等待循环启动
        
        async def _init():
            global memory_engine, workflow_agent, embed_model
            embed_model = APIEmbedModel(
                base_url=os.getenv("EMBED_API_BASE"),
                model_name=os.getenv("EMBED_MODEL_NAME"),
                api_key=os.getenv("EMBED_API_KEY"),
                timeout=int(os.getenv("EMBED_TIMEOUT")),
                max_retries=int(os.getenv("EMBED_MAX_RETRIES")),
            )
            
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            resource_dir = os.path.join(project_root, 'resources')

            # 创建 KV Store
            kv_db_path = os.path.join(resource_dir, 'dbmstore.db')
            kv_store = DbmKVStore(kv_db_path)

            # 创建语义存储
            semantic_store = ChromaSemanticStore(resource_dir, embed_model)

            # 创建数据库存储
            path = Path(f"{resource_dir}/news_sql_db.db").resolve()
            db_store = DefaultDbStore(create_async_engine(f"sqlite+aiosqlite:///{path}"))

            # 注册存储
            MemoryEngine.register_store(kv_store=kv_store, semantic_store=semantic_store, db_store=db_store)

            memory_engine = await MemoryEngine.create_mem_engine_instance(sys_config)
            memory_engine.set_group_llm_config(
                "news", 
                ModelConfig(
                    "siliconflow", 
                    BaseModelInfo(
                        api_key=API_KEY, 
                        api_base=API_BASE, 
                        model=MODEL_NAME,  
                    )
                )
            )
            workflow_agent = create_memory_workflow_agent()

        # 在全局事件循环中运行初始化
        run_coroutine_in_global_loop(_init())
        is_initialized = True

@app.route('/add_conversation', methods=['POST'])
def add_conversation():
    """添加对话记忆"""
    # 确保已初始化
    if not is_initialized:
        init_memory_engine_sync()

    data = request.json
    user_id = data.get('user_id')
    message = data.get('message')
    # message += "。我可以有多个兴趣爱好"
    global memory_engine
    if not user_id or not message:
        return jsonify({'error': 'Missing required parameters'}), 400

    async def _add_conversation_async():
        messages = BaseMessage(role="user", content=message)
        timestamp = datetime.now()
        # 添加用户画像
        msg_id = await memory_engine.add_conversation_messages(user_id=user_id, group_id="news", messages=[messages], timestamp=timestamp)
        return {'status': 'success', 'user_id': user_id, 'msg_id': msg_id}

    try:
        result = run_coroutine_in_global_loop(_add_conversation_async())
        return jsonify(result)
    except Exception as e:
        logger.error(str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/add_profile', methods=['POST'])
def add_profile():
    """添加用户画像"""
    # 确保已初始化
    if not is_initialized:
        init_memory_engine_sync()

    data = request.json
    user_id = data.get('user_id')
    message = data.get('message')
    # message += "。我可以有多个兴趣爱好"
    global memory_engine
    if not user_id or not message:
        return jsonify({'error': 'Missing required parameters'}), 400
    global data_id_generator
    async def _add_profile_async():
        msg_id = await data_id_generator.generate_next_id(user_id)
        memory = UserProfileUnit(MemoryType.USER_PROFILE, user_id, "news", "兴趣爱好", message, mem_id=msg_id)
        llm_service = ModelFactory().get_model('siliconflow', API_KEY, API_BASE)
        # 添加用户画像
        await memory_engine.user_profile_manager.add(memory, (MODEL_NAME, llm_service))
        return {'status': 'success', 'user_id': user_id, 'msg_id': msg_id}

    try:
        result = run_coroutine_in_global_loop(_add_profile_async())
        return jsonify(result)
    except Exception as e:
        logger.error(str(e))
        return jsonify({"error": str(e)}), 500
    
@app.route('/delete_mem', methods=['POST'])
def delete_mem():
    """删除记忆"""
    # 确保已初始化
    if not is_initialized:
        init_memory_engine_sync()

    data = request.json
    user_id = data.get('user_id')
    msg_id = data.get('msg_id')
    # message += "。我可以有多个兴趣爱好"
    global memory_engine
    if not user_id or not msg_id:
        return jsonify({'error': 'Missing required parameters'}), 400

    async def _delete_mem_async():
        # 删除记忆
        await memory_engine.delete_mem_by_id(user_id=user_id, group_id="news", mem_id=msg_id)
        return {'status': 'success', 'user_id': user_id}

    try:
        result = run_coroutine_in_global_loop(_delete_mem_async())
        return jsonify(result)
    except Exception as e:
        logger.error(str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/delete_profile', methods=['POST'])
def delete_profile():
    """删除用户画像"""
    # 确保已初始化
    if not is_initialized:
        init_memory_engine_sync()

    data = request.json
    user_id = data.get('user_id')
    msg_id = data.get('msg_id')
    # message += "。我可以有多个兴趣爱好"
    global memory_engine
    if not user_id or not msg_id:
        return jsonify({'error': 'Missing required parameters'}), 400
    
    async def _delete_profile_async():
        # 删除记忆
        await memory_engine.user_profile_manager.delete(user_id=user_id, group_id="news", mem_id=msg_id)
        return {'status': 'success', 'user_id': user_id}
    
    try:
        result = run_coroutine_in_global_loop(_delete_profile_async())
        return jsonify(result)
    except Exception as e:
        logger.error(str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/update_profile', methods=['POST'])
def update_profile():
    """更新用户画像"""
    # 确保已初始化
    if not is_initialized:
        init_memory_engine_sync()

    data = request.json
    user_id = data.get('user_id')
    msg_id = data.get('msg_id')
    value = data.get('value')
    global memory_engine
    if not user_id or not msg_id or not value:
        return jsonify({'error': 'Missing required parameters'}), 400

    async def _update_profile_async():
        # 更新用户画像
        await memory_engine.user_profile_manager.update(user_id=user_id, group_id="news", mem_id=msg_id, new_memory=value)
        return {'status': 'success', 'user_id': user_id}

    try:
        result = run_coroutine_in_global_loop(_update_profile_async())
        return jsonify(result)
    except Exception as e:
        logger.error(str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/get_profile/<user_id>', methods=['GET'])
def get_profile(user_id):
    """获取用户画像"""
    # 确保已初始化
    if not is_initialized:
        init_memory_engine_sync()

    global memory_engine

    async def _get_profile_async():
        user_profiles = await memory_engine.list_user_mem(user_id=user_id, group_id="news", num=20, page=1)
        if not user_profiles:
            user_profiles = []
        profiles = []
        for result in user_profiles:
            profiles.append(result['mem'])
        return {
            'user_id': user_id,
            'profile': profiles
        }

    try:
        result = run_coroutine_in_global_loop(_get_profile_async())
        return jsonify(result)
    except Exception as e:
        logger.error(str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/get_recent_news/<user_id>', methods=['POST'])
def get_recent_news(user_id):
    """获取新闻列表"""
    data = request.get_json()
    api_key = data.get('api_key')
    key_words = data.get('key_words', '')
    country = data.get('country', "cn,us,kr")
    language = data.get('language', "zh,zht,en")

    if not is_initialized:
        init_memory_engine_sync()

    async def _get_news_async():
        try:
            # 确保key_words是字符串格式
            if not key_words:
                # 如果没有关键词，使用默认关键词
                key_words_str = "AI OR 大模型 OR 量子计算"
            elif isinstance(key_words, list):
                key_words_str = " OR ".join(key_words)
            else:
                key_words_str = key_words
                
            raw_data = get_news(api_key, key_words_str, country, language)
            return {
                'user_id': user_id,
                'result': raw_data
            }
        except Exception as e:
            logger.error(f"获取新闻失败: {str(e)}")
            # 返回模拟数据作为备用
            return {
                'user_id': user_id,
                'result': [
                    {"id": 1, "title": "测试新闻1", "source_name": "测试来源", "pub_date": "2023-10-01", "description": "这是一条测试新闻1的描述"},
                    {"id": 2, "title": "测试新闻2", "source_name": "测试来源", "pub_date": "2023-10-01", "description": "这是一条测试新闻2的描述"},
                    {"id": 3, "title": "测试新闻3", "source_name": "测试来源", "pub_date": "2023-10-01", "description": "这是一条测试新闻3的描述"}
                ]
            }
    try:
        result = run_coroutine_in_global_loop(_get_news_async())
        final_response = { 
                 "user_id": result["user_id"], 
                 "raw_data": result["result"]  # 或者保持为字符串，看前端需求 
             } 
        return jsonify(final_response)
    except Exception as e:
        logger.error(f"处理get_recent_news请求时出错: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/generate_news/<user_id>', methods=['POST'])
def generate_news(user_id):
    data = request.get_json()
    raw_data = data.get('raw_data', [])
    logger.debug(f"raw_data: {raw_data}")

    """生成新闻简报"""
    # 确保已初始化
    if not is_initialized:
        init_memory_engine_sync()

    async def _generate_news_async():
        # 创建一个局部变量来使用，避免修改外部函数的变量
        local_raw_data = raw_data.copy() if isinstance(raw_data, list) else raw_data
        filter_data = []
        for l_data in local_raw_data:
            ft = {
                "title": l_data.get("title"),
                "description": l_data.get("description"),
                "url": l_data.get("url")
            }
            filter_data.append(ft)

        # 获取用户画像
        profile_results = await memory_engine.list_user_mem(user_id=user_id, group_id="news", num=20, page=1)
        profiles = []
        # 确保profile_results不是None，避免NoneType object is not iterable错误
        if profile_results:
            for result in profile_results:
                profiles.append(result['mem'])
        user_profile = {
            'user_id': user_id,
            'profile': profiles
        }
        if not isinstance(filter_data, (list, tuple)):
            filter_data = []

        global workflow_agent

        result = await workflow_agent.invoke({
            "user_id": user_id,
            "user_profile": json.dumps(user_profile),  # 使用JSON格式化而不是直接str()
            "raw_data": json.dumps(filter_data),
            "query": "生成今天的晨间简报"
        })

        return {
            'user_id': user_id,
            'result': result
        }

    try:
            output_result = run_coroutine_in_global_loop(_generate_news_async())
            # 安全地访问嵌套字典键
            result = None
            if output_result and isinstance(output_result, dict):
                if 'result' in output_result and isinstance(output_result['result'], dict):
                    if 'output' in output_result['result']:
                        if hasattr(output_result['result']['output'], 'result'):
                            output_result_result = output_result['result']['output'].result
                            if isinstance(output_result_result, dict) and 'responseContent' in output_result_result:
                                result = output_result_result['responseContent']
                            elif isinstance(output_result_result, dict):
                                # 如果没有responseContent字段，直接使用result
                                result = output_result_result
                            else:
                                # 如果result不是字典，直接使用
                                result = output_result_result
            
            actual_data = None
            if result:
                if isinstance(result, str):
                    # 如果result是字符串，尝试提取JSON内容
                    json_match = re.search(r"```json\n(.*?)```", result, re.DOTALL)
                    if json_match:
                        actual_data = json_match.group(1).strip()
                    else:
                        # 如果没有JSON标记，尝试直接解析字符串
                        actual_data = result
                else:
                    # 如果result不是字符串，转换为JSON字符串
                    actual_data = json.dumps(result)
            logger.info(actual_data)
            final_response = {
                "user_id": output_result["user_id"],
                "news_list": actual_data  # 或者保持为字符串，看前端需求
            }
            return jsonify(final_response)
    except Exception as e:
        logger.error(str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # 启动时初始化
    init_memory_engine_sync()

    # 运行Flask应用
    app.run(host='127.0.0.1', port=9000, debug=True, use_reloader=False)
