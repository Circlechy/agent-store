import streamlit as st
import os
import time
import pandas as pd
import json
from openjiuwen.core.utils.llm.messages import BaseMessage
from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory
import requests
from openjiuwen.core.common.logging import logger

BASE_URL = "http://127.0.0.1:9000"
USER_ID = "user_001"

# 设置环境变量
API_BASE = os.getenv("API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
# 为了满足BaseModelInfo的验证要求，提供一个非空的默认API密钥（实际使用时需要替换为真实密钥）
API_KEY = os.getenv("API_KEY", "sk-3b15e251510747c28b569bdf214bf7c2")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen-plus-latest")
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai")  # 使用小写的openai以匹配model_library中的实现
os.environ["LLM_SSL_VERIFY"] = "False"

# ---------------------------------------------------------
# 配置与设置
# ---------------------------------------------------------
st.set_page_config(
    page_title="个性化智能资讯Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

try:
    model = ModelFactory().get_model(
            model_provider=MODEL_PROVIDER,
            api_base=API_BASE,
            api_key=API_KEY,
        )
except Exception as e:
    st.error(f"初始化 AI 客户端失败。请检查配置。错误信息: {e}")
    model = None

# ---------------------------------------------------------
# 自定义 CSS
# ---------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background-color: #f8f9fa;
    }

    /* 侧边栏样式 */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e5e7eb;
    }

    /* 折叠面板样式 */
    .stExpander {
        background-color: white;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        border: 1px solid #e5e7eb;
        margin-bottom: 1rem;
    }

    /* 按钮 */
    div.stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s;
    }

    /* 状态指示器 */
    .status-dot {
        height: 10px;
        width: 10px;
        background-color: #bbb;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
    }
    .status-active { background-color: #22c55e; box-shadow: 0 0 8px #22c55e; }
    .status-inactive { background-color: #ef4444; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------# 状态管理# ---------------------------------------------------------# 1. 用户画像 / 长期记忆

# 从profile_service获取用户画像
def get_user_profile(user_id):
    url = f"{BASE_URL}/get_profile/{user_id}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            st.success(f"成功获取用户画像: {len(data.get('profile', []))} 条记录", icon="✅")
            return data.get('profile', [])
        else:
            st.error(f"获取用户画像失败: {response.status_code} - {response.text}")
            return []
    except requests.exceptions.ConnectionError as e:
        st.error(f"连接失败，无法访问用户画像服务: {e}")
        st.info("请确保profile_service.py已经启动并运行在9000端口", icon="ℹ️")
        return []
    except Exception as e:
        st.error(f"请求用户画像接口异常: {e}")
        st.info(f"尝试访问的URL: {url}", icon="ℹ️")
        return []

# 确保在应用启动时始终获取最新的用户画像
# 不使用initialized标志，每次页面加载都检查是否有后端数据
# 这样可以确保刷新后能获取到最新保存的用户画像
if 'memories' not in st.session_state or not st.session_state.memories:
    st.session_state.memories = get_user_profile(USER_ID)
    
# 添加一个刷新按钮
if st.button("🔄 刷新用户画像", use_container_width=False):
    st.session_state.memories = get_user_profile(USER_ID)
    st.rerun()

# 从profile_service获取新闻
def get_news_from_service(user_id, api_key, key_words, country="cn", language="zh"):
    url = f"{BASE_URL}/get_recent_news/{user_id}"
    try:
        # 将用户画像转换为字符串格式作为输入
        if isinstance(key_words, list):
            user_profile = "\n".join(key_words)
        else:
            user_profile = key_words
        
        # 使用大模型生成3-5个中英文关键词
        if model:
            with st.spinner("正在生成新闻检索关键词..."):
                prompt = f"""
你是一位专业的关键词提取专家。
请根据用户画像内容，提取5个最能代表用户兴趣的中英文关键词。

用户画像：
{user_profile}

输出格式要求：
1. 生成5个关键词
2. 用逗号分隔
3. 只输出关键词，不要添加任何解释或说明
4. 确保关键词具有新闻检索价值

例如：
AI,机器学习,深度学习,特朗普
"""
                
                try:
                    result = model.invoke(
                        model_name=MODEL_NAME,
                        messages=[BaseMessage(role="user", content=prompt)]
                    )
                    logger.info(result)
                    # 解析大模型输出，提取关键词
                    generated_keywords = result.content
                    st.success(f"生成的关键词: {generated_keywords}", icon="🔍")
                    
                    # 使用生成的关键词
                    key_words_str = str(generated_keywords).replace(",", " OR ")
                    logger.info(f"生成的关键字:{key_words_str}")
                except Exception as model_error:
                    st.warning(f"大模型生成关键词失败，将使用原始用户画像: {model_error}")
                    #  fallback到原始逻辑
                    if isinstance(key_words, list):
                        key_words_str = " OR ".join(key_words)
                    else:
                        key_words_str = key_words
        else:
            st.warning("AI客户端未初始化，将使用原始用户画像作为关键词")
            # fallback到原始逻辑
            if isinstance(key_words, list):
                key_words_str = " OR ".join(key_words)
            else:
                key_words_str = key_words
        
        # 调用profile service获取新闻
        response = requests.post(url, json={
            "api_key": api_key,
            "key_words": key_words_str,
            "country": country,
            "language": language
        })
        
        if response.status_code == 200:
            data = response.json()
            return data.get('result', [])
        else:
            st.error(f"获取新闻失败: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        st.error(f"请求新闻接口异常: {e}")
        return []

# 通过profile_service生成新闻简报
def generate_news_brief(user_id, raw_data):
    url = f"{BASE_URL}/generate_news/{user_id}"
    try:
        response = requests.post(url, json={"raw_data": raw_data})
        if response.status_code == 200:
            data = response.json()
            return data.get('news_list', "生成简报失败")
        else:
            st.error(f"生成简报失败: {response.status_code} - {response.text}")
            return "生成简报失败"
    except Exception as e:
        st.error(f"请求生成简报接口异常: {e}")
        return "生成简报失败"

# 2. 聊天记录
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# 3. Agent 状态
if 'agent_running' not in st.session_state:
    st.session_state.agent_running = False

if 'generated_brief' not in st.session_state:
    st.session_state.generated_brief = None

if 'news' not in st.session_state:
    st.session_state.news = []

# 模拟新闻数据
SAMPLE_NEWS = [
    {"title": "OpenAI 发布 GPT-5 预览版", "source": "TechCrunch", "summary": "推理能力和多模态处理有显著性能提升。", "time": "10:30"},
    {"title": "Python 3.14 JIT 编译器更新", "source": "Python.org", "summary": "新的 JIT 编译器优化显示数据密集型工作负载速度提升 20%。", "time": "09:15"},
    {"title": "React Server Components 最佳实践", "source": "Frontend Mastery", "summary": "深入探讨最新 React 架构下的状态管理和数据获取。", "time": "昨天"}
]

# ---------------------------------------------------------
# AI 服务
# ---------------------------------------------------------

def generate_brief():
    if not model:
        return "AI 客户端未初始化。"

    memory_context = "\n".join(st.session_state.memories)
    news_context = "\n".join([f"- {n['title']} ({n['source']}): {n['summary']}" for n in SAMPLE_NEWS])

    prompt = f"""
你是一位精英个人助理。

用户画像 / 长期记忆:
{memory_context}

最新新闻源:
{news_context}

任务:
为用户生成一份简明扼要、高价值的“每日简报”。
1. 亲切地问候用户。
2. 综合新闻条目，根据用户画像强调其价值。
3. 保持专业、鼓舞人心，字数控制在 300 字以内。
4. 使用 Markdown 格式。
5. **请全程使用中文回答**。
"""

    try:
        completion = model.invoke(
            model_name="qwen-plus-latest",
            messages=[BaseMessage(role="user", content=prompt)]
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"生成简报时出错: {str(e)}"

# ---------------------------------------------------------
# 侧边栏导航与控制
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 20px;">
            <div style="width: 32px; height: 32px; background: #2563eb; border-radius: 8px;
                        display: flex; align-items: center; justify-content: center;
                        color: white; font-weight: bold;">W</div>
            <h2 style="margin: 0; font-size: 1.2rem; color: #1f2937;">个性化智能资讯Agent</h2>
        </div>
    """, unsafe_allow_html=True)

    # 导航
    view = st.radio("导航", ["控制台", "对话"], label_visibility="collapsed")
    st.divider()

    # Agent 服务控制
    st.markdown("### ⚙️ 服务控制")

    status_class = "status-active" if st.session_state.agent_running else "status-inactive"
    status_text = "运行中" if st.session_state.agent_running else "已停止"

    st.markdown(f"""
        <div style="background: #f3f4f6; padding: 10px; border-radius: 8px;
                    display: flex; align-items: center; margin-bottom: 15px;">
            <span class="status-dot {status_class}"></span>
            <span style="font-weight: 500; font-size: 0.9rem;">Agent 状态: {status_text}</span>
        </div>
    """, unsafe_allow_html=True)

    if st.session_state.agent_running:
        if st.button("⏹ 停止 Agent", type="secondary", use_container_width=True):
            st.session_state.agent_running = False
            st.session_state.news = []  # 清空新闻数据
            st.rerun()
    else:
        if st.button("▶ 启动 Agent", type="primary", use_container_width=True):
            st.session_state.agent_running = True
            api_key = "pub_2fb5680cc9634869a0bafce3e7906806"
            # 使用用户画像作为关键词
            key_words = st.session_state.memories
            country = "cn"
            language = "zh"
            
            # 从profile_service获取新闻
            with st.spinner("正在获取最新新闻..."):
                st.session_state.raw_data = get_news_from_service(USER_ID, api_key, key_words, country, language)
                if not st.session_state.raw_data:
                    st.error("获取新闻失败")
                    st.stop()
                # 将新闻数据保存到session_state
                st.session_state.news = st.session_state.raw_data

            with st.spinner("正在执行 Workflow 任务并生成简报..."):
                # 通过profile_service生成新闻简报
                st.session_state.generated_brief = generate_news_brief(USER_ID, st.session_state.raw_data)
            st.rerun()

    if st.session_state.agent_running:
        st.info("Agent 正在监控任务。", icon="⚡")

# ---------------------------------------------------------
# 主应用逻辑
# ---------------------------------------------------------

if view == "控制台":
    st.title("仪表盘")
    st.markdown("管理您的用户画像并查看个性化洞察。")

    # 加载用户画像
    if not st.session_state.memories:
        st.session_state.memories = get_user_profile(USER_ID)

    if st.button("💾 保存配置", use_container_width=False):
        if not st.session_state.memories:
            st.warning("没有可保存的用户画像或记忆。")
        else:
            # 保存新的画像
            session = requests.Session()
            
            # 先清空原有画像 - 目前没有清空接口，所以只添加新的
            st.info("正在保存用户画像...", icon="⏳")
            
            # 保存所有画像条目
            success_count = 0
            error_count = 0
            
            for profile_text in st.session_state.memories:
                payload = {
                    "user_id": USER_ID,  # 用户唯一 ID
                    "message": profile_text  # 用户画像文本
                }
                url = f"{BASE_URL}/add_profile"
                try:
                    response = session.post(url, json=payload, timeout=10)
                    if response.status_code == 200:
                        success_count += 1
                    else:
                        error_count += 1
                        st.warning(f"保存画像失败: {response.text}")
                except Exception as e:
                    error_count += 1
                    st.error(f"保存用户画像失败: {e}")
            
            if error_count == 0:
                st.toast(f"成功保存 {success_count} 条用户画像！", icon="✅")
                # 保存成功后，重新获取最新的用户画像，确保本地状态与后端同步
                st.session_state.memories = get_user_profile(USER_ID)
            else:
                st.toast(f"保存完成，但有 {error_count} 条失败。", icon="⚠️")
                # 即使有部分失败，也尝试获取最新的用户画像
                st.session_state.memories = get_user_profile(USER_ID)
    st.markdown("---")

    # --------------------------
# 用户画像编辑区
# --------------------------
    with st.expander("🧠 用户画像 (长期记忆)", expanded=True):
        st.info("管理用户画像与长期偏好。", icon="ℹ️")
        st.caption("提示：选中左侧行号并按 'Delete' 键删除条目。")
        
        # 预定义用户画像选项（当用户画像为空时使用）
        predefined_profiles = [
            "关注科技行业最新发展",
            "对人工智能领域感兴趣",
            "关注OpenAI产品动态",
        ]
        
        # 当用户画像为空时，使用预定义画像
        if not st.session_state.memories:
            st.session_state.memories = predefined_profiles.copy()
        
        df_memories = pd.DataFrame(st.session_state.memories, columns=["content"])

        edited_memories = st.data_editor(
            df_memories,
            num_rows="dynamic",
            column_config={
                "content": st.column_config.TextColumn("画像内容", required=True)
            },
            use_container_width=True,
            key="memory_editor"
        )

        if not edited_memories.empty:
            st.session_state.memories = edited_memories["content"].tolist()
        else:
            st.session_state.memories = []

    # --------------------------
    # 情报展示
    # --------------------------
    st.markdown("### 每日情报")

    # 1. 每日简报
    with st.container(border=True):
        st.subheader("✨ 每日简报")
        
        # 添加Agent运行按钮
        if st.button("▶ 运行Agent生成简报", use_container_width=False):
            with st.spinner("正在运行Agent生成简报..."):
                if not st.session_state.raw_data and st.session_state.news:
                    st.session_state.raw_data = st.session_state.news
                    
                if st.session_state.raw_data:
                    # 通过profile_service生成新闻简报
                    st.session_state.generated_brief = generate_news_brief(USER_ID, st.session_state.raw_data)
                    st.success("简报生成完成!")
                else:
                    st.error("没有可用的新闻数据，请先获取新闻")
            st.rerun()
        
        if st.session_state.generated_brief:
            try:
                # 尝试将生成的简报解析为JSON
                brief_data = json.loads(st.session_state.generated_brief)
                
                # 将JSON格式的简报转换为Markdown格式
                markdown_content = ""
                
                # 检查brief_data是否为列表
                if isinstance(brief_data, list):
                    for item in brief_data:
                        if isinstance(item, dict):
                            category = item.get('category', '未分类')
                            content = item.get('content', '')
                            url = item.get('url', '')
                            
                            # 使用卡片组件美化展示
                            with st.container(border=True, key=f"brief_card_{category}"):
                                # 分类标题
                                st.markdown(f"**{category}**")
                                # 内容
                                st.markdown(f"{content}")
                                # 如果有URL，添加链接
                                if url:
                                    st.markdown(f"📎 [阅读全文]({url})")
                else:
                    # 如果不是列表，直接显示
                    markdown_content = st.session_state.generated_brief
            except json.JSONDecodeError:
                # 如果解析失败，直接显示原始内容
                markdown_content = st.session_state.generated_brief
            
            # 显示Markdown内容
            if markdown_content:
                st.markdown(markdown_content)
            st.caption(f"最后更新: {time.strftime('%H:%M')}")
        else:
            st.info("暂无简报。请点击“运行Agent生成简报”按钮。", icon="👈")

    # 2. 每日资讯
    with st.container(border=True):
        st.subheader("📰 每日资讯")
        
        # 添加获取最新新闻的按钮在每日资讯框内
        if st.button("🔄 获取最新新闻", use_container_width=True):
            with st.spinner("正在获取最新新闻..."):
                # 使用用户画像作为关键词
                key_words = st.session_state.memories
                # 使用默认的API_KEY - 实际使用时可以让用户配置
                api_key = "pub_2fb5680cc9634869a0bafce3e7906806"
                country = "cn"
                language = "zh"
                
                # 从profile_service获取新闻
                st.session_state.news = get_news_from_service(USER_ID, api_key, key_words, country, language)
                if not st.session_state.news:
                    st.error("获取新闻失败")
                else:
                    st.success(f"成功获取 {len(st.session_state.news)} 条新闻")
                    
                    # 只更新原始数据，不自动生成简报
                    st.session_state.raw_data = st.session_state.news
                st.rerun()
        
        # 每日资讯内容展示
        if st.session_state.news:
            for idx, news in enumerate(st.session_state.news):
                # 确保新闻数据结构符合预期，适配memory_workflow_agent.py返回的格式
                title = news.get('title', '无标题')
                source = news.get('source_name', '未知来源')
                time = news.get('pub_date', '未知时间')
                description = news.get('description', '无摘要')
                url = news.get('url', '#')
                
                # 使用卡片组件美化新闻展示
                with st.container(border=True, key=f"news_card_{idx}"):
                    # 标题行
                    col_title, col_source = st.columns([4, 2])
                    with col_title:
                        st.markdown(f"<h4 style='margin-bottom: 5px;'>{title}</h4>", unsafe_allow_html=True)
                    with col_source:
                        st.markdown(f"<div style='text-align: right; color: #666; font-size: 0.85em;'>{source} • {time}</div>", unsafe_allow_html=True)
                    
                    # 摘要行
                    st.markdown(f"<p style='color: #333; margin: 10px 0;'>{description}</p>", unsafe_allow_html=True)
                    
                    # 元数据和链接行
                    col_meta, col_link = st.columns([3, 1])
                    with col_meta:
                        st.markdown(f"<span style='color: #999; font-size: 0.8em;'>国家: {news.get('country', '未知')} • 语言: {news.get('language', '未知')}</span>", unsafe_allow_html=True)
                    with col_link:
                        st.markdown(f"<div style='text-align: right;'><a href='{url}' target='_blank' style='color: #1a73e8; text-decoration: none;'>阅读全文 →</a></div>", unsafe_allow_html=True)
        else:
            st.info("暂无新闻。请点击'获取最新新闻'按钮。", icon="👆")
        
        # 查看所有来源按钮
        if st.button("查看所有来源", use_container_width=True) and st.session_state.news:
            with st.expander("所有新闻来源", expanded=True):
                sources = set(news.get('source_name', '未知来源') for news in st.session_state.news)
                for source in sorted(sources):
                    st.markdown(f"📰 {source}")

elif view == "对话":
    st.title("智能对话助手")

    # 显示聊天记录
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 聊天输入
    if prompt := st.chat_input("根据您的用户画像或新闻提问..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        if model:
            try:
                system_instruction = f"""
你是 WorkflowAgent，一个乐于助人的助手。

用户画像 / 长期记忆:
{st.session_state.memories}

请始终根据记忆中定义的用户偏好行事。
**请用中文回复**。
"""

                messages = [BaseMessage(content=system_instruction, role="user")]

                for m in st.session_state.chat_history:
                    role = "user" if m["role"] == "user" else "assistant"
                    messages.append(BaseMessage(content=m["content"], role=role))


                completion = model.invoke(
                    model_name="qwen-plus-latest",
                    messages=messages
                )

                response_text = completion.choices[0].message.content

                st.session_state.chat_history.append(
                    {"role": "assistant", "content": response_text}
                )

                with st.chat_message("assistant"):
                    st.markdown(response_text)

            except Exception as e:
                st.error(f"生成回复时出错: {e}")
        else:
            st.error("AI 模型未连接。")