"""
DeepDigest Lite - Streamlit 主应用
Web 界面，串联 Day Agent 和 Night Agent
"""

import sys
import asyncio
import time
import re
from pathlib import Path
from datetime import datetime

# ===================== 事件循环初始化（必须在最前面）=====================
# OpenJiuwen 框架在初始化时需要事件循环，必须在导入其他模块之前设置
def _ensure_event_loop():
    """确保存在事件循环"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Event loop is closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop

# 在导入任何 OpenJiuwen 相关模块之前设置事件循环
_ensure_event_loop()

# 确保项目路径在 sys.path 中
# deep_digest/src/ui/app.py -> deep_digest/ 需要往上3层
DEEP_DIGEST_ROOT = Path(__file__).parent.parent.parent  # deep_digest/
PROJECT_ROOT = DEEP_DIGEST_ROOT.parent  # agent-core/

# 添加两个路径以支持不同的导入方式
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(DEEP_DIGEST_ROOT) not in sys.path:
    sys.path.insert(0, str(DEEP_DIGEST_ROOT))

import streamlit as st

# 导入渲染组件
from src.ui.renderers import (
    inject_css, 
    render_card, 
    render_empty_state, 
    render_inbox_counter
)

# 导入工具和配置
from src.config import get_model_config
from src.tools.inbox_tools import count_pending_fragments, add_fragment
from src.tools.memory_tools import get_all_cards, update_card, export_to_markdown, export_cards_to_markdown, delete_card_by_id, get_random_card, get_cards_from_last_days
from src.agents.day_agent import create_day_agent
from src.agents.night_agent import create_night_agent
from src.agents.knowledge_agent import create_knowledge_agent

# 导入多模态感知工具
try:
    from src.tools.sense_tools import process_image, process_file, process_audio
    SENSE_TOOLS_AVAILABLE = True
except ImportError:
    SENSE_TOOLS_AVAILABLE = False
    print("⚠️ 多模态感知工具不可用")

# 导入 P0 新增功能
try:
    from src.tools.backup_tools import (
        create_backup, 
        list_backups, 
        restore_backup, 
        delete_backup,
        auto_backup
    )
    BACKUP_AVAILABLE = True
except ImportError:
    BACKUP_AVAILABLE = False
    print("⚠️ 备份功能不可用")

try:
    from src.utils.logger import get_logger
    LOGGER_AVAILABLE = True
except ImportError:
    LOGGER_AVAILABLE = False
    print("⚠️ 日志功能不可用")

# 导入 P1 新增功能
try:
    from src.tools.embedding_tools import (
        init_openai_client,
        generate_card_embeddings,
        search_cards_semantic,
        search_cards_hybrid,
        recommend_related_cards
    )
    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False
    print("⚠️ 向量检索功能不可用")

try:
    from src.tools.scheduler_tools import (
        setup_auto_dreaming,
        setup_auto_backup,
        list_jobs,
        stop_scheduler,
        get_notifications,
        mark_notifications_read
    )
    SCHEDULER_AVAILABLE = True
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False
    NOTIFICATIONS_AVAILABLE = False
    print("⚠️ 调度器功能不可用")


# ===================== 页面配置 =====================
st.set_page_config(
    page_title="DeepDigest Lite",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入 CSS 样式（兼容性调用）
inject_css()


# ===================== 自动刷新组件 =====================

@st.fragment(run_every="5s")
def auto_refresh_inbox_counter():
    """
    自动刷新的 Inbox 计数器
    每 5 秒自动检查一次待处理碎片数量，实现浏览器采集后的实时更新
    """
    pending_count = count_pending_fragments()
    
    # 检测数量变化，触发提示
    if "last_pending_count" not in st.session_state:
        st.session_state.last_pending_count = pending_count
    
    # 如果数量增加了，显示新采集提示
    if pending_count > st.session_state.last_pending_count:
        new_count = pending_count - st.session_state.last_pending_count
        st.toast(f"🎉 新增 {new_count} 条采集！", icon="📥")
    
    st.session_state.last_pending_count = pending_count
    
    # 渲染计数器
    render_inbox_counter(pending_count)
    
    return pending_count


# ===================== 辅助函数 =====================

def run_async(coro):
    """在同步环境中运行异步协程"""
    loop = _ensure_event_loop()
    return loop.run_until_complete(coro)


@st.cache_resource
def get_cached_model_config():
    """缓存模型配置（避免重复加载）"""
    return get_model_config()


def init_embedding_client():
    """
    初始化 Embedding 客户端
    
    Returns:
        bool: 是否初始化成功
    """
    if not EMBEDDING_AVAILABLE:
        return False
    
    try:
        import os
        api_key = os.getenv("LLM_API_KEY")
        api_base = os.getenv("LLM_API_BASE", "https://openrouter.ai/api/v1")
        
        if not api_key:
            return False
        
        init_openai_client(api_key, api_base)
        return True
    except Exception as e:
        print(f"⚠️ Embedding 客户端初始化失败: {e}")
        return False


def render_chat_message_with_card_links(content: str, message_index: int = 0):
    """
    渲染带卡片链接的聊天消息
    将卡片链接转换为内联的小按钮，放在对应内容末尾
    
    Args:
        content: 消息内容
        message_index: 消息在历史中的索引（用于生成唯一 key）
    """
    # 按段落分割，每个段落可能包含卡片链接
    # 使用正则找出所有 [xxx](CARD_ID:yyy) 格式的链接位置
    
    # 定义链接模式
    link_pattern = r'\[([^\]]+)\]\(CARD_ID:([a-f0-9\-]{8,})\)'
    
    # 分割内容为段落
    paragraphs = content.split('\n')
    
    button_counter = 0
    
    for para_idx, paragraph in enumerate(paragraphs):
        if not paragraph.strip():
            st.markdown("")  # 空行
            continue
        
        # 查找该段落中的所有卡片链接
        links_in_para = re.findall(link_pattern, paragraph)
        
        if not links_in_para:
            # 没有链接，清理可能的残留标记后直接渲染
            clean_para = paragraph
            clean_para = re.sub(r'<查看[^>]*卡片[^>]*>', '', clean_para)
            clean_para = re.sub(r'<[^>]*卡片>', '', clean_para)
            clean_para = re.sub(r'<>\s*', '', clean_para)
            clean_para = re.sub(r'🔗\s*', '', clean_para)
            if clean_para.strip():
                st.markdown(clean_para)
        else:
            # 有链接，移除链接文本，然后渲染段落+按钮
            clean_para = re.sub(link_pattern, '', paragraph)
            clean_para = re.sub(r'<查看[^>]*卡片[^>]*>', '', clean_para)
            clean_para = re.sub(r'<[^>]*卡片>', '', clean_para)
            clean_para = re.sub(r'<>\s*', '', clean_para)
            clean_para = re.sub(r'🔗\s*', '', clean_para)
            clean_para = re.sub(r'。\s*。', '。', clean_para)
            
            # 渲染段落文本
            if clean_para.strip():
                st.markdown(clean_para)
            
            # 在段落末尾渲染小按钮（内联风格）
            # 去重
            seen_ids = set()
            unique_links = []
            for link_text, card_id in links_in_para:
                if card_id not in seen_ids:
                    seen_ids.add(card_id)
                    unique_links.append((link_text, card_id))
            
            if unique_links:
                # 内联显示小链接按钮（水平排列）
                link_cols = st.columns(len(unique_links) + 2)  # 额外列用于留白
                for idx, (link_text, card_id) in enumerate(unique_links):
                    with link_cols[idx]:
                        st.markdown('<div class="card-link-btn">', unsafe_allow_html=True)
                        if st.button(
                            "🔗 查看卡片", 
                            key=f"card_btn_{message_index}_{para_idx}_{button_counter}",
                            help=f"点击跳转查看完整卡片",
                        ):
                            st.session_state["_jumping_to_card"] = True
                            st.session_state.active_tab = "📰 Daily Feed"
                            st.session_state.card_search_query = card_id
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
                        button_counter += 1


def format_datetime(iso_string: str) -> str:
    """格式化 ISO 时间字符串"""
    if not iso_string:
        return "暂无"
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%m-%d %H:%M")
    except:
        return iso_string[:10] if len(iso_string) > 10 else iso_string


def get_latest_card_time(cards: list) -> str:
    """获取最新卡片的时间"""
    if not cards:
        return "暂无"
    
    # 按时间排序
    sorted_cards = sorted(
        cards, 
        key=lambda x: x.get("created_at", ""), 
        reverse=True
    )
    
    if sorted_cards:
        return format_datetime(sorted_cards[0].get("created_at", ""))
    return "暂无"


def calculate_time_saved(cards: list) -> float:
    """
    计算累计节省时间（小时）
    
    假设：
    - 人工整理一条碎片需要 2 分钟
    - 撰写一张结构化卡片需要 5 分钟
    
    公式：(fragments_count * 2) + (cards_count * 5) 分钟
    
    Args:
        cards: 所有卡片列表
    
    Returns:
        float: 节省时间（小时，保留 1 位小数）
    """
    if not cards:
        return 0.0
    
    # 统计卡片数量
    cards_count = len(cards)
    
    # 统计所有卡片的源碎片数量
    fragments_count = 0
    for card in cards:
        source_ids = card.get("source_fragment_ids", [])
        if isinstance(source_ids, list):
            fragments_count += len(source_ids)
        elif source_ids:  # 单个 ID 的情况
            fragments_count += 1
    
    # 计算总节省时间（分钟）
    total_minutes = (fragments_count * 2) + (cards_count * 5)
    
    # 转换为小时，保留 1 位小数
    return round(total_minutes / 60, 1)


def get_dynamic_greeting() -> dict:
    """
    根据当前时间返回动态问候语
    
    Returns:
        dict: 包含 title 和 greeting 的字典
    """
    current_hour = datetime.now().hour
    
    if 6 <= current_hour < 12:
        # 上午 (6:00 - 12:00)
        return {
            "title": "🌞 早安，DeepDigest",
            "greeting": "新的一天，先处理最重要的事情吧！🎯"
        }
    elif 12 <= current_hour < 18:
        # 下午 (12:00 - 18:00)
        return {
            "title": "☕ 下午好，DeepDigest",
            "greeting": "进度如何？别忘了站起来活动一下，保持精力。💪"
        }
    else:
        # 晚上 (18:00 - 6:00)
        return {
            "title": "🌙 晚上好，DeepDigest",
            "greeting": "今天辛苦了！整理一下思绪，准备休息吧。💤"
        }


def confirm_complete_todo(todo_id: str, todo_title: str):
    """确认完成待办事项的二次确认对话框"""
    if st.button("✅ 确认完成", key=f"confirm_yes_{todo_id}", type="primary"):
        try:
            delete_card_by_id(todo_id)
            st.toast(f"✅ 已完成: {todo_title}", icon="✅")
            st.session_state.pop(f"confirm_delete_{todo_id}", None)  # 清除确认状态
            st.rerun()
        except Exception as e:
            st.error(f"删除失败: {e}")
    
    if st.button("❌ 取消", key=f"confirm_no_{todo_id}"):
        st.session_state.pop(f"confirm_delete_{todo_id}", None)
        st.rerun()


def get_weekday_name(date_obj) -> str:
    """获取中文星期名称"""
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return weekdays[date_obj.weekday()]


def render_daily_feed():
    """
    渲染 Daily Feed 知识流页面
    包含搜索框、日期轮播、分类标签页、分页功能
    """
    from datetime import date, timedelta
    
    st.header("📰 知识流")
    st.caption("AI 整理后的结构化知识卡片")
    
    # ===================== Session State 初始化 =====================
    # 初始化选中日期（默认今天）
    if "selected_date" not in st.session_state:
        st.session_state.selected_date = date.today()
    
    # 存储上一次的日期，用于检测日期切换
    if "previous_selected_date" not in st.session_state:
        st.session_state.previous_selected_date = st.session_state.selected_date
    
    # 初始化搜索模式状态
    if "feed_search_mode" not in st.session_state:
        st.session_state.feed_search_mode = False
    
    # 加载所有卡片
    all_cards = get_all_cards()
    current_pending = count_pending_fragments()
    
    # ===================== 0. 搜索框（折叠式，支持 Chat/卡片链接 跳转）=====================
    # 获取跳转过来的搜索词
    default_search = st.session_state.get("card_search_query", "")
    is_jumping = st.session_state.get("_jumping_to_card", False)
    
    # 如果是跳转，强制使用跳转的搜索词（绕过 text_input 的状态缓存问题）
    if is_jumping and default_search:
        # 直接使用跳转搜索词，不经过 text_input
        search_term = default_search
        search_expanded = True
        
        # 显示搜索框（只读展示）
        with st.expander("🔍 搜索知识库", expanded=True):
            st.info(f"🔍 正在搜索: **{default_search}**")
            if st.button("✖ 清除搜索", key="clear_jump_search", use_container_width=True):
                st.session_state.card_search_query = ""
                st.session_state.feed_search_mode = False
                st.session_state._jumping_to_card = False
                st.rerun()
        
        # 清理跳转状态（下次刷新时恢复正常搜索框）
        st.session_state._jumping_to_card = False
        st.session_state.card_search_query = ""
    else:
        # 正常模式：使用 text_input
        search_expanded = bool(default_search)
        
        with st.expander("🔍 搜索知识库", expanded=search_expanded):
            search_col1, search_col2 = st.columns([5, 1])
            with search_col1:
                search_term = st.text_input(
                    "搜索",
                    placeholder="输入关键词、标签或卡片ID（如：cd85424a）",
                    value=default_search,
                    key="daily_feed_search_input",
                    label_visibility="collapsed"
                )
            with search_col2:
                if search_term:
                    if st.button("✖ 清除", key="clear_search", use_container_width=True):
                        st.session_state.card_search_query = ""
                        st.session_state.feed_search_mode = False
                        st.rerun()
    
    # ===================== 搜索模式：直接显示搜索结果 =====================
    if search_term:
        st.session_state.feed_search_mode = True
        search_lower = search_term.lower()
        
        # 搜索过滤（支持标题、标签、卡片ID、摘要）
        filtered_cards = [
            c for c in all_cards
            if (search_lower in c.get("title", "").lower() or
                any(search_lower in tag.lower() for tag in c.get("tags", [])) or
                search_lower in c.get("id", "").lower() or
                search_lower in c.get("summary", "").lower())
        ]
        
        st.caption(f"🔍 找到 {len(filtered_cards)} / {len(all_cards)} 张匹配的卡片")
        
        if not filtered_cards:
            render_empty_state(
                f"未找到包含 \"{search_term}\" 的卡片。\n\n尝试其他关键词或清除搜索。",
                "🔍"
            )
        else:
            # 按时间倒序排列搜索结果
            sorted_results = sorted(
                filtered_cards,
                key=lambda x: x.get("created_at", ""),
                reverse=True
            )
            for card in sorted_results:
                render_card(card, all_cards=all_cards, context="daily_feed")
        
        return  # 搜索模式下不显示日期轮播
    
    # ===================== 1. 顶部：横向日期轮播 (Date Carousel) =====================
    selected_date = st.session_state.selected_date
    
    # --- 第一行：年份和月份切换 ---
    year_month_col1, year_month_col2, year_month_col3, year_month_col4, year_month_col5 = st.columns([1, 2, 1, 2, 1])
    
    with year_month_col1:
        if st.button("◀", key="prev_year", help="上一年", use_container_width=True):
            new_date = selected_date.replace(year=selected_date.year - 1)
            st.session_state.selected_date = new_date
            st.rerun()
    
    with year_month_col2:
        st.markdown(f"<h4 style='text-align: center; margin: 0;'>{selected_date.year}年</h4>", unsafe_allow_html=True)
    
    with year_month_col3:
        if st.button("▶", key="next_year", help="下一年", use_container_width=True):
            new_date = selected_date.replace(year=selected_date.year + 1)
            st.session_state.selected_date = new_date
            st.rerun()
    
    with year_month_col4:
        # 月份切换
        month_col_left, month_col_center, month_col_right = st.columns([1, 2, 1])
        with month_col_left:
            if st.button("◀◀", key="prev_month", help="上一月"):
                if selected_date.month == 1:
                    new_date = selected_date.replace(year=selected_date.year - 1, month=12, day=1)
                else:
                    new_date = selected_date.replace(month=selected_date.month - 1, day=1)
                st.session_state.selected_date = new_date
                st.rerun()
        with month_col_center:
            st.markdown(f"<h4 style='text-align: center; margin: 0;'>{selected_date.month}月</h4>", unsafe_allow_html=True)
        with month_col_right:
            if st.button("▶▶", key="next_month", help="下一月"):
                if selected_date.month == 12:
                    new_date = selected_date.replace(year=selected_date.year + 1, month=1, day=1)
                else:
                    new_date = selected_date.replace(month=selected_date.month + 1, day=1)
                st.session_state.selected_date = new_date
                st.rerun()
    
    with year_month_col5:
        # 快速回到今天
        if st.button("📍今天", key="go_today", help="回到今天", use_container_width=True):
            st.session_state.selected_date = date.today()
            st.rerun()
    
    st.markdown("---")
    
    # --- 第二行：日期导航（显示前后各2天，共5天）---
    date_cols = st.columns(5)
    
    for i, offset in enumerate(range(-2, 3)):  # -2, -1, 0, 1, 2
        target_date = selected_date + timedelta(days=offset)
        is_selected = (offset == 0)
        is_today = (target_date == date.today())
        
        # 按钮文本：日期 + 星期
        day_str = str(target_date.day)
        weekday_str = get_weekday_name(target_date)
        btn_label = f"{day_str}\n{weekday_str}"
        
        # 添加今天标记
        if is_today and not is_selected:
            btn_label = f"📍{day_str}\n{weekday_str}"
        
        with date_cols[i]:
            btn_type = "primary" if is_selected else "secondary"
            if st.button(
                btn_label,
                key=f"date_btn_{target_date.isoformat()}",
                type=btn_type,
                use_container_width=True
            ):
                st.session_state.selected_date = target_date
                st.rerun()
    
    st.divider()
    
    # ===================== 检测日期切换，重置页码 =====================
    if st.session_state.selected_date != st.session_state.previous_selected_date:
        # 日期变化，清除所有分页状态
        keys_to_reset = [k for k in st.session_state.keys() if k.startswith("page_")]
        for key in keys_to_reset:
            del st.session_state[key]
        st.session_state.previous_selected_date = st.session_state.selected_date
    
    # ===================== 2. 中间：数据分流与统计 =====================
    selected_date_str = selected_date.isoformat()
    
    # 过滤当天卡片
    day_cards = [
        c for c in all_cards
        if c.get("created_at", "").startswith(selected_date_str)
    ]
    
    # 分类卡片
    todos = [c for c in day_cards if c.get("type") == "todo"]
    techs = [c for c in day_cards if c.get("type") == "tech"]
    ideas = [c for c in day_cards if c.get("type") == "idea"]
    
    # 其他类型归入 ideas
    other_types = [c for c in day_cards if c.get("type") not in ["todo", "tech", "idea"]]
    ideas.extend(other_types)
    
    # 每日概览
    total_count = len(day_cards)
    todo_count = len(todos)
    
    overview_text = f"📅 {selected_date_str} 概览：今日共记录 **{total_count}** 条内容"
    if todo_count > 0:
        overview_text += f"，包含 **{todo_count}** 个待办"
    overview_text += "。"
    
    st.caption(overview_text)
    
    # ===================== 2. 分类标签页与分页 =====================
    
    # 如果当天没有任何卡片
    if not day_cards:
        render_empty_state(
            f"📅 {selected_date_str} 暂无知识卡片记录。\n\n快去 Record 页面记录一些碎片，然后点击 'Start Dreaming' 吧！",
            "📭"
        )
        return
    
    # 创建分类标签页（标题带数字）
    # 根据上次删除的卡片类型调整 tab 顺序，保持用户在同一 tab
    last_type = st.session_state.pop("last_deleted_card_type", None)
    
    if last_type == "tech":
        # 技术笔记放在第一位
        tab_titles = [
            f"💻 技术 ({len(techs)})",
            f"✅ 待办 ({len(todos)})",
            f"💡 灵感 ({len(ideas)})"
        ]
        tab_tech, tab_todo, tab_idea = st.tabs(tab_titles)
    elif last_type == "idea":
        # 灵感想法放在第一位
        tab_titles = [
            f"💡 灵感 ({len(ideas)})",
            f"✅ 待办 ({len(todos)})",
            f"💻 技术 ({len(techs)})"
        ]
        tab_idea, tab_todo, tab_tech = st.tabs(tab_titles)
    else:
        # 默认顺序（待办在第一位）
        tab_titles = [
            f"✅ 待办 ({len(todos)})",
            f"💻 技术 ({len(techs)})",
            f"💡 灵感 ({len(ideas)})"
        ]
        tab_todo, tab_tech, tab_idea = st.tabs(tab_titles)
    
    # --- Tab 1: 待办清单（不分页）---
    with tab_todo:
        if not todos:
            st.info("🎉 今日无待办，一身轻松！")
        else:
            # 按 deadline 升序排序（紧急在前）
            def get_deadline_sort_key(card):
                deadline = card.get("deadline")
                if not deadline:
                    return "9999-99-99"  # 无截止日期排最后
                return deadline
            
            sorted_todos = sorted(todos, key=get_deadline_sort_key)
            
            st.caption(f"共 {len(sorted_todos)} 个待办事项，按截止日期排序")
            
            for card in sorted_todos:
                render_card(card, all_cards=all_cards, context="daily_feed")
    
    # --- Tab 2: 技术笔记（分页）---
    with tab_tech:
        render_paginated_cards(
            cards=techs,
            all_cards=all_cards,
            tab_name="tech",
            selected_date=selected_date,
            page_size=5,
            empty_message="🍃 今日未记录技术笔记..."
        )
    
    # --- Tab 3: 灵感想法（分页）---
    with tab_idea:
        render_paginated_cards(
            cards=ideas,
            all_cards=all_cards,
            tab_name="idea",
            selected_date=selected_date,
            page_size=5,
            empty_message="🍃 今日未记录灵感想法..."
        )


def render_paginated_cards(
    cards: list,
    all_cards: list,
    tab_name: str,
    selected_date,
    page_size: int = 5,
    empty_message: str = "🍃 今日未记录..."
):
    """
    渲染带分页的卡片列表
    
    Args:
        cards: 当前分类的卡片列表
        all_cards: 所有卡片（用于知识链功能）
        tab_name: 标签名（用于生成唯一的 session_state key）
        selected_date: 选中的日期
        page_size: 每页显示数量
        empty_message: 空状态消息
    """
    if not cards:
        st.info(empty_message)
        return
    
    # 按创建时间倒序排序
    sorted_cards = sorted(
        cards,
        key=lambda x: x.get("created_at", ""),
        reverse=True
    )
    
    total_cards = len(sorted_cards)
    total_pages = (total_cards + page_size - 1) // page_size  # 向上取整
    
    # 生成唯一的页码 key
    page_key = f"page_{selected_date.isoformat()}_{tab_name}"
    
    # 初始化页码
    if page_key not in st.session_state:
        st.session_state[page_key] = 1
    
    current_page = st.session_state[page_key]
    
    # 确保页码有效
    if current_page < 1:
        current_page = 1
    if current_page > total_pages:
        current_page = total_pages
    
    st.session_state[page_key] = current_page
    
    # 计算当前页的卡片范围
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_cards)
    
    # 显示统计
    st.caption(f"共 {total_cards} 条记录，显示第 {start_idx + 1}-{end_idx} 条")
    
    # 渲染当前页的卡片
    page_cards = sorted_cards[start_idx:end_idx]
    for card in page_cards:
        render_card(card, all_cards=all_cards, context="daily_feed")
    
    # 分页导航
    if total_pages > 1:
        st.markdown("---")
        nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
        
        with nav_col1:
            if current_page > 1:
                if st.button("◀ 上一页", key=f"prev_{page_key}", use_container_width=True):
                    st.session_state[page_key] = current_page - 1
                    st.rerun()
            else:
                st.button("◀ 上一页", key=f"prev_{page_key}", disabled=True, use_container_width=True)
        
        with nav_col2:
            st.markdown(
                f"<p style='text-align: center; margin-top: 8px;'>第 {current_page}/{total_pages} 页</p>",
                unsafe_allow_html=True
            )
        
        with nav_col3:
            if current_page < total_pages:
                if st.button("下一页 ▶", key=f"next_{page_key}", use_container_width=True):
                    st.session_state[page_key] = current_page + 1
                    st.rerun()
            else:
                st.button("下一页 ▶", key=f"next_{page_key}", disabled=True, use_container_width=True)


@st.dialog("📋 核心看板", width="large")
def show_daily_reminder_dialog():
    """显示每日待办提醒弹窗（GTD 风格）"""
    # 获取动态问候语
    greeting_info = get_dynamic_greeting()
    
    st.markdown(f"### {greeting_info['title']}")
    st.caption(f"*{greeting_info['greeting']}*")
    st.caption(f"📅 {datetime.now().strftime('%Y年%m月%d日 %H:%M')}")
    
    st.divider()
    
    # 初始化已删除任务列表
    if "deleted_todos_in_dialog" not in st.session_state:
        st.session_state.deleted_todos_in_dialog = []
    
    # 加载所有卡片
    cards = get_all_cards()
    pending_count = count_pending_fragments()
    
    # 过滤掉已在弹窗中删除的任务
    cards = [c for c in cards if c.get('id') not in st.session_state.deleted_todos_in_dialog]
    
    # 统计信息
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📚 知识卡片", f"{len(cards)} 张")
    with col2:
        st.metric("📥 待处理碎片", pending_count)
    with col3:
        todo_cards = [c for c in cards if c.get("type") == "todo"]
        st.metric("📝 待办事项", f"{len(todo_cards)} 项")
    
    st.divider()
    
    # ==================== 1. 待办事项区域（GTD 风格排序）====================
    if todo_cards:
        # 自定义背景区域
        st.markdown("""
        <div style="background-color: #FFF3E0; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
            <h4 style="margin-top: 0;">📝 待办事项 (Action Items)</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # GTD 排序算法
        def get_deadline_priority(todo):
            """计算待办的优先级（越小越优先）"""
            deadline = todo.get("deadline")
            if not deadline:
                return (4, "")  # 无日期，优先级最低
            
            try:
                from datetime import date
                deadline_date = date.fromisoformat(deadline)
                today = date.today()
                delta = (deadline_date - today).days
                
                if delta < 0:  # 已逾期
                    return (1, deadline_date)
                elif delta == 0:  # 今天截止
                    return (2, deadline_date)
                else:  # 未来任务
                    return (3, deadline_date)
            except:
                return (4, "")
        
        # 按 GTD 原则排序，只显示前5条
        sorted_todos = sorted(todo_cards, key=get_deadline_priority)[:5]
        
        # 用于标记是否有任务被删除（本次渲染）
        any_todo_deleted = False
        
        for todo in sorted_todos:
            # 计算截止状态
            deadline = todo.get("deadline")
            status_text = ""
            status_color = "info"
            
            if deadline:
                try:
                    from datetime import date
                    deadline_date = date.fromisoformat(deadline)
                    today = date.today()
                    delta = (deadline_date - today).days
                    
                    if delta < 0:
                        status_text = f"已逾期 {-delta} 天"
                        status_color = "error"
                    elif delta == 0:
                        status_text = "今天截止"
                        status_color = "success"
                    elif delta == 1:
                        status_text = "明天截止"
                        status_color = "warning"
                    else:
                        status_text = f"{deadline} ({delta} 天后)"
                        status_color = "info"
                except:
                    pass
            
            todo_id = todo.get('id')
            todo_title = todo.get('title', '无标题')
            
            with st.container(border=True):
                col_content, col_action = st.columns([7.5, 2.5])
                
                with col_content:
                    st.markdown(f"**{todo_title}**")
                    if todo.get('summary'):
                        st.caption(todo['summary'])
                    # 显示截止状态
                    if status_text:
                        if status_color == "error":
                            st.error(status_text, icon="🔴")
                        elif status_color == "success":
                            st.success(status_text, icon="🟢")
                        elif status_color == "warning":
                            st.warning(status_text, icon="🟡")
                        else:
                            st.info(status_text, icon="📅")
                
                with col_action:
                    # 使用 popover 实现二次确认
                    with st.popover("✅", use_container_width=True):
                        st.write("确认完成吗？")
                        if st.button("确认完成", key=f"confirm_{todo_id}", type="primary", use_container_width=True):
                            print(f"[Debug] 准备删除卡片: {todo_id}, 标题: {todo_title}")
                            try:
                                success = delete_card_by_id(todo_id)
                                print(f"[Debug] 删除结果: {success}")
                                if success:
                                    # 添加到已删除列表
                                    st.session_state.deleted_todos_in_dialog.append(todo_id)
                                    any_todo_deleted = True
                                    st.success(f"✅ 已完成: {todo_title}", icon="✅")
                                else:
                                    st.error("删除失败：未找到该卡片")
                            except Exception as e:
                                print(f"[Debug] 删除异常: {e}")
                                import traceback
                                traceback.print_exc()
                                st.error(f"删除失败: {e}")
        
        # 如果有任务被删除，显示提示并提供刷新按钮
        if any_todo_deleted:
            st.info("💡 任务已完成并删除，点击下方按钮刷新列表", icon="ℹ️")
            if st.button("🔄 刷新待办列表", type="secondary", use_container_width=True):
                st.rerun()
    else:
        st.markdown("""
        <div style="background-color: #FFF3E0; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
            <h4 style="margin-top: 0;">📝 待办事项 (Action Items)</h4>
        </div>
        """, unsafe_allow_html=True)
        st.info("🎉 暂无待办事项，保持这个状态！")
    
    st.divider()
    
    # ==================== 2. 昨日新知回顾区域 ====================
    st.markdown("""
    <div style="background-color: #E3F2FD; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
        <h4 style="margin-top: 0;">🧠 昨日新知回顾 (Insights Review)</h4>
    </div>
    """, unsafe_allow_html=True)
    
    # 筛选昨日卡片
    from datetime import date, timedelta
    yesterday = date.today() - timedelta(days=1)
    yesterday_str = yesterday.isoformat()
    
    knowledge_cards = [c for c in cards if c.get("type") != "todo"]
    
    # 优先筛选昨日生成的卡片
    yesterday_cards = [
        c for c in knowledge_cards
        if c.get("created_at", "").startswith(yesterday_str)
    ]
    
    # 如果昨天没有，回退到最新的
    display_cards = yesterday_cards[:3] if yesterday_cards else sorted(
        knowledge_cards,
        key=lambda x: x.get("created_at", ""),
        reverse=True
    )[:3]
    
    if display_cards:
        if not yesterday_cards:
            st.caption("💡 昨天没有新卡片，以下是最新的知识：")
        
        for card in display_cards:
            with st.container(border=True):
                # 类型图标
                type_icons = {
                    "tech": "💻",
                    "idea": "💡",
                    "note": "📝"
                }
                icon = type_icons.get(card.get("type"), "📄")
                
                col_icon, col_content = st.columns([0.5, 9.5])
                with col_icon:
                    st.markdown(icon)
                with col_content:
                    st.markdown(f"**{card.get('title', '无标题')}**")
                    if card.get('summary'):
                        st.caption(card['summary'])
                    # 标签
                    if card.get('tags'):
                        tags_str = " ".join([f"`#{tag}`" for tag in card['tags'][:3]])
                        st.markdown(tags_str)
                    st.caption(f"🕐 {format_datetime(card.get('created_at', ''))}")
    else:
        st.info("暂无知识卡片，快去记录一些想法吧！")
    
    st.divider()
    
    # 提示信息
    if pending_count > 0:
        st.warning(f"💡 你有 **{pending_count}** 条待处理碎片，点击侧边栏的 **'🌙 Start Dreaming'** 开始整理吧！")
    
    # 关闭按钮
    col_left, col_center, col_right = st.columns([1, 1, 1])
    with col_center:
        if st.button("✓ 知道了", type="primary", use_container_width=True):
            # 清除已删除任务列表
            st.session_state.deleted_todos_in_dialog = []
            st.session_state.daily_reminder_shown = True
            st.rerun()
            st.rerun()


# ===================== Sidebar =====================

with st.sidebar:
    st.title("🧠 DeepDigest Lite")
    st.caption("你的第二大脑 - 碎片整理 & 知识蒸馏")
    
    st.divider()
    
    # 显示通知
    if NOTIFICATIONS_AVAILABLE:
        unread_notifications = get_notifications(unread_only=True)
        if unread_notifications:
            with st.expander(f"🔔 通知 ({len(unread_notifications)})", expanded=True):
                for notif in reversed(unread_notifications[-3:]):  # 只显示最近3条
                    notif_type = notif.get("type", "info")
                    message = notif.get("message", "")
                    timestamp = notif.get("timestamp", "")
                    
                    # 根据类型选择图标和颜色
                    if notif_type == "success":
                        st.success(message, icon="✅")
                    elif notif_type == "error":
                        st.error(message, icon="❌")
                    elif notif_type == "warning":
                        st.warning(message, icon="⚠️")
                    else:
                        st.info(message, icon="ℹ️")
                    
                    st.caption(f"⏰ {timestamp[:19]}")
                
                # 标记已读按钮
                if st.button("✓ 全部标记为已读", key="mark_read", use_container_width=True):
                    mark_notifications_read()
                    st.rerun()
            
            st.divider()
    
    # 实时计数器（自动刷新，每 5 秒检测一次浏览器采集）
    pending_count = auto_refresh_inbox_counter()
    
    # 知识卡片统计
    all_cards = get_all_cards()
    
    st.divider()
    
    # ===================== 数据仪表盘 (Dashboard) =====================
    with st.expander("📊 数据概览", expanded=True):
        # 2x2 网格布局，适应窄宽度
        dash_row1_col1, dash_row1_col2 = st.columns(2)
        
        with dash_row1_col1:
            st.metric(
                label="📚 知识库",
                value=f"{len(all_cards)} 张",
                delta="卡片" if all_cards else None,
                delta_color="off"
            )
        
        with dash_row1_col2:
            st.metric(
                label="📥 待处理",
                value=pending_count,
                delta="需整理" if pending_count > 0 else "已清空",
                delta_color="inverse" if pending_count > 0 else "off"
            )
        
        dash_row2_col1, dash_row2_col2 = st.columns(2)
        
        with dash_row2_col1:
            time_saved = calculate_time_saved(all_cards)
            st.metric(
                label="⏳ 节省",
                value=f"{time_saved} h",
                delta="效率提升" if time_saved > 0 else None,
                delta_color="normal",
                help="基于人工整理碎片(2分/条)和撰写文档(5分/篇)的平均耗时估算"
            )
        
        with dash_row2_col2:
            latest_time = get_latest_card_time(all_cards)
            st.metric(
                label="🕐 更新",
                value=latest_time,
                delta="活跃" if all_cards else None,
                delta_color="off"
            )
    
    st.divider()
    
    # 待办提醒按钮
    if st.button("📋 核心看板", use_container_width=True):
        st.session_state.daily_reminder_shown = False
        st.rerun()
    
    st.divider()
    
    # Start Dreaming 按钮 (升级版交互)
    if st.button("🌙 Start Dreaming (整理)", use_container_width=True, type="primary"):
        if pending_count == 0:
            st.warning("📭 Inbox 为空，没有需要整理的碎片")
        else:
            # 使用 st.status 展示 Agent 思考过程
            with st.status("🌙 DeepDigest 正在启动...", expanded=True) as status:
                try:
                    # Step 1: 扫描 Inbox
                    st.write("📥 正在扫描海马体 (Inbox)...")
                    time.sleep(0.5)  # 模拟处理时间
                    st.write(f"   发现 {pending_count} 条待处理碎片")
                    
                    # Step 2: 激活大脑皮层
                    st.write("🧠 激活大脑皮层，正在进行语义聚类...")
                    time.sleep(0.3)
                    
                    # Step 3: 检索长期记忆
                    st.write("🔗 检索长期记忆，构建知识图谱...")
                    st.write(f"   已加载 {len(all_cards)} 条历史记忆")
                    time.sleep(0.3)
                    
                    # Step 4: 创建并执行 Night Agent
                    st.write("⚡ 启动 Night Agent 执行知识蒸馏...")
                    st.write("   💡 提示：根据碎片数量，这可能需要1-3分钟...")
                    model_config = get_cached_model_config()
                    night_agent = create_night_agent(model_config)
                    
                    # 执行工作流
                    result = run_async(night_agent.invoke(inputs={}))
                    
                    # Step 5: 熵减清理
                    st.write("🧹 执行熵减清理...")
                    time.sleep(0.3)
                    
                    # 解析结果 - 从workflow返回值中提取统计数据
                    # workflow返回格式: 
                    # {'output': WorkflowOutput(result={...}, state=...), 'result_type': 'answer'}
                    # 需要访问: result['output'].result['output']['result']
                    cards_saved = 0
                    fragments_deleted = 0
                    
                    def find_stats(obj, depth=0):
                        """递归查找统计数据，支持字典和对象属性"""
                        if depth > 10:  # 防止无限递归
                            return None
                        
                        # 处理字典
                        if isinstance(obj, dict):
                            # 检查当前层级是否包含目标字段
                            if "cards_saved" in obj and "fragments_deleted" in obj:
                                return {
                                    "cards_saved": obj.get("cards_saved", 0),
                                    "fragments_deleted": obj.get("fragments_deleted", 0)
                                }
                            
                            # 递归查找所有值
                            for key, value in obj.items():
                                found = find_stats(value, depth + 1)
                                if found:
                                    return found
                        
                        # 处理对象属性（如 WorkflowOutput）
                        elif hasattr(obj, '__dict__'):
                            # 尝试常见的属性名
                            for attr_name in ['result', 'output', 'data']:
                                if hasattr(obj, attr_name):
                                    found = find_stats(getattr(obj, attr_name), depth + 1)
                                    if found:
                                        return found
                        
                        return None
                    
                    if result:
                        # 调试：打印result结构
                        print(f"🔍 Workflow返回结果: {result}")
                        
                        stats = find_stats(result)
                        if stats:
                            cards_saved = stats["cards_saved"]
                            fragments_deleted = stats["fragments_deleted"]
                            print(f"✅ 成功提取统计: cards_saved={cards_saved}, fragments_deleted={fragments_deleted}")
                        else:
                            print(f"⚠️ 未能从返回结果中提取统计数据")
                    
                    # 更新状态为完成
                    status.update(
                        label=f"✨ 整理完成！生成 {cards_saved} 张卡片，清理 {fragments_deleted} 条碎片", 
                        state="complete",
                        expanded=False
                    )
                    
                    # 庆祝动画
                    st.balloons()
                    
                    # 短暂延迟后刷新
                    time.sleep(1)
                    st.rerun()
                    
                except Exception as e:
                    status.update(label="❌ 整理失败", state="error")
                    st.error(f"错误: {str(e)}")
                    import traceback
                    with st.expander("查看错误详情"):
                        st.code(traceback.format_exc())
    
    st.divider()
    
    # 工具箱
    with st.expander("🔧 工具箱"):
        # 备份与恢复
        if BACKUP_AVAILABLE:
            st.subheader("💾 备份与恢复")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📦 创建备份", use_container_width=True):
                    try:
                        backup_path = create_backup()
                        st.success(f"✅ 备份成功！\n{backup_path}")
                    except Exception as e:
                        st.error(f"❌ 备份失败: {e}")
            
            with col2:
                if st.button("📋 查看备份", use_container_width=True):
                    backups = list_backups()
                    if backups:
                        st.write(f"共有 {len(backups)} 个备份")
                    else:
                        st.info("暂无备份")
            
            st.divider()
        
        # 导出 Markdown（支持全部导出和批量选择导出）
        st.subheader("📄 导出 Markdown")
        
        # 导出模式选择
        export_mode = st.radio(
            "导出模式",
            ["全部导出", "批量选择"],
            horizontal=True,
            key="export_mode",
            label_visibility="collapsed"
        )
        
        if export_mode == "全部导出":
            # === 全部导出 ===
            if st.button("📥 导出所有卡片", use_container_width=True):
                try:
                    md_content = export_to_markdown()
                    st.session_state["export_md_content"] = md_content
                    st.session_state["export_filename"] = f"knowledge_export_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                    st.session_state["export_success_msg"] = "✅ 导出成功！"
                    st.rerun()  # 刷新页面以显示下载按钮
                except Exception as e:
                    st.error(f"❌ 导出失败: {e}")
        else:
            # === 批量选择导出 ===
            all_cards_for_export = get_all_cards()
            
            if not all_cards_for_export:
                st.info("📭 暂无卡片可导出")
            else:
                # 初始化选择状态
                if "export_selected_ids" not in st.session_state:
                    st.session_state["export_selected_ids"] = set()
                
                # 按类型分组显示
                cards_by_type = {"tech": [], "todo": [], "idea": []}
                for card in all_cards_for_export:
                    card_type = card.get("type", "tech")
                    if card_type in cards_by_type:
                        cards_by_type[card_type].append(card)
                
                type_labels = {"tech": "💻 技术笔记", "todo": "✅ 待办", "idea": "💡 灵感"}
                
                # 快捷选择按钮
                quick_col1, quick_col2, quick_col3 = st.columns(3)
                with quick_col1:
                    if st.button("全选", key="select_all_export", use_container_width=True):
                        # 更新选中集合
                        st.session_state["export_selected_ids"] = {c.get("id") for c in all_cards_for_export}
                        # 同步更新所有 checkbox 的 key
                        for c in all_cards_for_export:
                            st.session_state[f"export_card_{c.get('id')}"] = True
                        for ct in type_labels.keys():
                            st.session_state[f"select_all_{ct}"] = True
                        st.rerun()
                with quick_col2:
                    if st.button("清空", key="clear_all_export", use_container_width=True):
                        # 清空选中集合
                        st.session_state["export_selected_ids"] = set()
                        # 同步更新所有 checkbox 的 key
                        for c in all_cards_for_export:
                            st.session_state[f"export_card_{c.get('id')}"] = False
                        for ct in type_labels.keys():
                            st.session_state[f"select_all_{ct}"] = False
                        st.rerun()
                with quick_col3:
                    selected_count = len(st.session_state["export_selected_ids"])
                    st.caption(f"已选 {selected_count} 张")
                
                # 分类型展示卡片选择
                for card_type, label in type_labels.items():
                    type_cards = cards_by_type[card_type]
                    if not type_cards:
                        continue
                    
                    with st.expander(f"{label} ({len(type_cards)})", expanded=False):
                        # 按类型全选按钮
                        type_ids = {c.get("id") for c in type_cards}
                        all_type_selected = type_ids.issubset(st.session_state["export_selected_ids"])
                        
                        select_all_key = f"select_all_{card_type}"
                        if st.checkbox(
                            f"全选{label}", 
                            value=all_type_selected, 
                            key=select_all_key
                        ):
                            if not all_type_selected:
                                # 新勾选：选中该类型所有卡片
                                st.session_state["export_selected_ids"].update(type_ids)
                                for c in type_cards:
                                    st.session_state[f"export_card_{c.get('id')}"] = True
                                st.rerun()
                        else:
                            if all_type_selected:
                                # 取消勾选：取消该类型所有卡片
                                st.session_state["export_selected_ids"] -= type_ids
                                for c in type_cards:
                                    st.session_state[f"export_card_{c.get('id')}"] = False
                                st.rerun()
                        
                        # 逐张卡片选择
                        for card in type_cards:
                            card_id = card.get("id", "")
                            card_title = card.get("title", "无标题")
                            checkbox_key = f"export_card_{card_id}"
                            is_selected = card_id in st.session_state["export_selected_ids"]
                            
                            if st.checkbox(
                                f"{card_title[:25]}{'...' if len(card_title) > 25 else ''}",
                                value=is_selected,
                                key=checkbox_key,
                                help=f"ID: {card_id[:8]}..."
                            ):
                                st.session_state["export_selected_ids"].add(card_id)
                            else:
                                st.session_state["export_selected_ids"].discard(card_id)
                
                # 导出按钮
                selected_ids = st.session_state["export_selected_ids"]
                if selected_ids:
                    if st.button(f"📥 导出选中的 {len(selected_ids)} 张卡片", use_container_width=True):
                        try:
                            md_content = export_cards_to_markdown(list(selected_ids))
                            st.session_state["export_md_content"] = md_content
                            st.session_state["export_filename"] = f"knowledge_export_selected_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                            st.session_state["export_success_msg"] = f"✅ 成功导出 {len(selected_ids)} 张卡片！"
                            st.rerun()  # 刷新页面以显示下载按钮
                        except Exception as e:
                            st.error(f"❌ 导出失败: {e}")
                else:
                    st.button("📥 请先选择要导出的卡片", disabled=True, use_container_width=True)
        
        # 显示导出成功消息
        if st.session_state.get("export_success_msg"):
            st.success(st.session_state["export_success_msg"])
            st.session_state["export_success_msg"] = None  # 只显示一次
        
        # 显示下载按钮
        if st.session_state.get("export_md_content"):
            st.download_button(
                label="⬇️ 下载 Markdown 文件",
                data=st.session_state["export_md_content"],
                file_name=st.session_state.get("export_filename", f"knowledge_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"),
                mime="text/markdown",
                use_container_width=True
            )
            # 清除导出内容的按钮
            if st.button("🗑️ 清除导出", key="clear_export", use_container_width=True):
                st.session_state["export_md_content"] = None
                st.session_state["export_filename"] = None
                st.rerun()
        
        st.divider()
        
        # P1: 向量检索（已自动化，无需手动操作）
        if EMBEDDING_AVAILABLE:
            # 初始化客户端（静默初始化，用于后台语义搜索）
            init_embedding_client()
            # 注意：Embedding 生成已在 save_knowledge_cards() 中自动完成，无需手动触发
            # 知识链功能已集成到 renderers.py 中，使用 find_similar_card_ids 实现混合召回
        
        # P1: 定时任务
        if SCHEDULER_AVAILABLE:
            st.subheader("⏰ 定时任务")
            
            # 自动整理
            auto_dream = st.toggle(
                "🌙 自动整理",
                value=st.session_state.get("auto_dream_enabled", False),
                help="每天定时或达到阈值时自动整理碎片"
            )
            
            if auto_dream:
                dream_col1, dream_col2 = st.columns(2)
                with dream_col1:
                    dream_hour = st.number_input("时", 0, 23, 23, key="dream_hour")
                with dream_col2:
                    dream_minute = st.number_input("分", 0, 59, 0, key="dream_minute")
                
                dream_threshold = st.number_input(
                    "触发阈值（碎片数）",
                    min_value=1,
                    value=10,
                    key="dream_threshold"
                )
                
                if st.button("💾 保存配置", key="save_dream"):
                    try:
                        # 创建 Night Agent 工厂函数
                        def night_agent_factory():
                            model_config = get_model_config()
                            return create_night_agent(model_config)
                        
                        setup_auto_dreaming(
                            enabled=True,
                            hour=dream_hour,
                            minute=dream_minute,
                            threshold=dream_threshold,
                            agent_factory=night_agent_factory
                        )
                        st.session_state["auto_dream_enabled"] = True
                        st.success(f"✅ 已配置：每天 {dream_hour:02d}:{dream_minute:02d} 或达到 {dream_threshold} 条碎片时自动整理")
                    except Exception as e:
                        st.error(f"❌ 配置失败: {e}")
            else:
                if st.session_state.get("auto_dream_enabled", False):
                    try:
                        setup_auto_dreaming(enabled=False)
                        st.session_state["auto_dream_enabled"] = False
                        st.info("已禁用自动整理")
                    except Exception as e:
                        st.error(f"❌ 禁用失败: {e}")
            
            st.divider()
            
            # 自动备份
            auto_backup_enabled = st.toggle(
                "💾 自动备份",
                value=st.session_state.get("auto_backup_enabled", False),
                help="每天定时备份数据"
            )
            
            if auto_backup_enabled:
                backup_col1, backup_col2 = st.columns(2)
                with backup_col1:
                    backup_hour = st.number_input("时", 0, 23, 2, key="backup_hour")
                with backup_col2:
                    backup_minute = st.number_input("分", 0, 59, 0, key="backup_minute")
                
                if st.button("💾 保存配置", key="save_backup"):
                    try:
                        setup_auto_backup(
                            enabled=True,
                            hour=backup_hour,
                            minute=backup_minute
                        )
                        st.session_state["auto_backup_enabled"] = True
                        st.success(f"✅ 已配置：每天 {backup_hour:02d}:{backup_minute:02d} 自动备份")
                    except Exception as e:
                        st.error(f"❌ 配置失败: {e}")
            else:
                if st.session_state.get("auto_backup_enabled", False):
                    try:
                        setup_auto_backup(enabled=False)
                        st.session_state["auto_backup_enabled"] = False
                        st.info("已禁用自动备份")
                    except Exception as e:
                        st.error(f"❌ 禁用失败: {e}")
    
    st.divider()
    
    # 关于信息
    with st.expander("ℹ️ 关于"):
        st.markdown("""
        **DeepDigest Lite** 是一个基于 LLM 的知识管理工具。
        
        **核心概念：**
        - 📝 **Record**: 快速记录碎片想法
        - 🌙 **Dreaming**: 让 AI 整理你的碎片
        - 📚 **Feed**: 查看结构化的知识卡片
        
        **技术栈：**
        - OpenJiuwen Framework
        - Streamlit
        - SQLite + JSON
        """)


# ===================== Main Area (Tabs) =====================

# 初始化 session_state
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "📝 Record"
if "card_search_query" not in st.session_state:
    st.session_state.card_search_query = ""
if "_jumping_to_card" not in st.session_state:
    st.session_state._jumping_to_card = False

# 初始化每日提醒状态
if "daily_reminder_shown" not in st.session_state:
    st.session_state.daily_reminder_shown = False

# 在页面加载时显示每日提醒弹窗（仅首次）
if not st.session_state.daily_reminder_shown:
    st.session_state.daily_reminder_shown = True  # 立即标记为已显示，避免tab切换时重复弹出
    show_daily_reminder_dialog()

# Tab 导航（使用 pills 实现更易点击的导航）
tab_options = ["📝 Record", "📰 Daily Feed", "💬 Chat"]

# 确保当前 tab 在选项中
if st.session_state.active_tab not in tab_options:
    st.session_state.active_tab = tab_options[0]

selected_tab = st.pills(
    "导航",
    tab_options,
    selection_mode="single",
    default=st.session_state.active_tab,
    label_visibility="collapsed"
)

# 处理 tab 切换（包括用户点击和程序跳转）
if selected_tab and selected_tab != st.session_state.active_tab:
    # 检查是否是跳转触发的（如果是，保留搜索状态）
    is_jumping = st.session_state._jumping_to_card
    
    # 更新 active_tab
    st.session_state.active_tab = selected_tab
    
    # 非跳转场景：清除搜索状态
    if not is_jumping:
        st.session_state.card_search_query = ""
    
    st.rerun()

# 使用 session_state 中的 active_tab 作为真实显示（确保同步）
current_tab = st.session_state.active_tab

st.divider()

# --- Tab 1: Record ---
if current_tab == "📝 Record":
    st.header("📝 极速录入")
    st.caption("快速记录你的想法、待办、代码片段，支持文字、语音、图片和文档上传...")
    
    # 初始化语音转写状态
    if "voice_transcript" not in st.session_state:
        st.session_state.voice_transcript = None
    if "voice_processed_id" not in st.session_state:
        st.session_state.voice_processed_id = None
    if "voice_audio_key" not in st.session_state:
        st.session_state.voice_audio_key = 0  # 用于重置 audio_input 组件
    if "text_input_key" not in st.session_state:
        st.session_state.text_input_key = 0  # 用于重置文本输入框
    if "file_uploader_key" not in st.session_state:
        st.session_state.file_uploader_key = 0  # 用于重置文件上传组件
    
    # 统一的输入区域标签样式
    st.markdown("""
    <style>
    .input-label {
        font-size: 14px;
        font-weight: 500;
        color: #31333F;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .input-hint {
        font-size: 13px;
        color: #6B7280;
        font-weight: 400;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 1️⃣ 文本输入区域
    st.markdown('<p class="input-label">💭 文字输入 <span class="input-hint">- 支持任何格式的文本内容</span></p>', unsafe_allow_html=True)
    user_input = st.text_area(
        "文字输入",
        placeholder="技术笔记、待办事项、灵感想法...",
        height=120,
        key=f"record_text_input_{st.session_state.text_input_key}",
        label_visibility="collapsed"
    )
    
    # 2️⃣ 语音录入区域
    col_voice_left, col_voice_right = st.columns([4, 1])
    
    with col_voice_left:
        st.markdown('<p class="input-label">🎙️ 语音录入 <span class="input-hint">- 点击麦克风录音，自动转写为文字</span></p>', unsafe_allow_html=True)
    
    with col_voice_right:
        # 语音输入区域（使用动态 key 支持重置）
        audio_value = st.audio_input(
            label="录音",
            key=f"record_audio_input_{st.session_state.voice_audio_key}",
            help="点击录音，说完后停止",
            label_visibility="collapsed"
        )
    
    # 处理语音输入（转写后显示结果，用户手动保存）
    if audio_value is not None and st.session_state.voice_transcript is None:
        # 只有在没有转写结果时才处理新音频
        audio_id = hash(audio_value.getvalue()[:100] + str(audio_value.size).encode())
        
        # 只在未处理过时执行转写
        if audio_id != st.session_state.voice_processed_id:
            with st.spinner("⚡ Groq 正在转写..."):
                try:
                    # 调用 Groq 转写
                    transcript = process_audio(audio_value)
                    
                    # 检查是否转写成功
                    if transcript and not transcript.startswith("❌"):
                        # 保存转写结果
                        st.session_state.voice_transcript = transcript
                        st.session_state.voice_processed_id = audio_id
                        print(f"✅ [Voice] 转写完成: {transcript[:50]}...")
                    else:
                        st.error(f"❌ 语音转写失败: {transcript}")
                        
                except Exception as e:
                    st.error(f"❌ 语音处理失败: {str(e)}")
                    print(f"❌ [Voice] 处理异常: {str(e)}")
    
    # 如果有语音转写内容，显示转写结果和操作按钮
    if st.session_state.voice_transcript:
        # 初始化编辑模式状态
        if "voice_edit_mode" not in st.session_state:
            st.session_state.voice_edit_mode = False
        
        st.markdown("""
        <div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); 
                    border-radius: 12px; padding: 16px; margin: 12px 0;">
            <div style="color: white; font-weight: 600; margin-bottom: 8px;">
                ✅ 语音转写完成
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # 根据编辑模式显示不同内容
        if st.session_state.voice_edit_mode:
            # 编辑模式：显示文本输入框
            edited_text = st.text_area(
                "编辑转写内容",
                value=st.session_state.voice_transcript,
                height=100,
                key="voice_edit_textarea",
                label_visibility="collapsed"
            )
            
            col_confirm, col_cancel = st.columns([1, 1])
            with col_confirm:
                if st.button("✅ 确认修改", key="confirm_edit", type="primary", use_container_width=True):
                    st.session_state.voice_transcript = edited_text
                    st.session_state.voice_edit_mode = False
                    st.rerun()
            with col_cancel:
                if st.button("❌ 取消", key="cancel_edit", use_container_width=True):
                    st.session_state.voice_edit_mode = False
                    st.rerun()
        else:
            # 显示模式：显示转写文本
            st.markdown(f"""
            <div style="background: #f8f9fa; border-radius: 8px; padding: 12px; margin-bottom: 12px;">
                <p style="font-size: 15px; line-height: 1.6; margin: 0; color: #262730;">
                    {st.session_state.voice_transcript}
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # 操作按钮：三列布局
            col_save, col_edit, col_clear = st.columns([1, 1, 1])
            
            with col_save:
                if st.button("💾 保存到 Inbox", key="save_voice", type="primary", use_container_width=True):
                    voice_content = f"【语音笔记】\n{st.session_state.voice_transcript}"
                    fragment_id = add_fragment(voice_content)
                    if fragment_id:
                        st.toast("✅ 语音笔记已保存！", icon="🎙️")
                        print(f"✅ [Voice] 语音笔记已保存 (ID: {fragment_id})")
                        # 清除状态并重置音频输入组件
                        st.session_state.voice_transcript = None
                        st.session_state.voice_processed_id = None
                        st.session_state.voice_audio_key += 1
                        st.session_state.voice_edit_mode = False
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("❌ 保存失败")
            
            with col_edit:
                if st.button("✏️ 编辑", key="edit_voice", use_container_width=True):
                    st.session_state.voice_edit_mode = True
                    st.rerun()
            
            with col_clear:
                if st.button("🗑️ 清空重录", key="clear_voice", use_container_width=True):
                    print("[Debug] 清空重录按钮被点击")
                    st.session_state.voice_transcript = None
                    st.session_state.voice_processed_id = None
                    # 通过更新 key 来重置 audio_input 组件，清除已录制的音频
                    st.session_state.voice_audio_key += 1
                    st.session_state.voice_edit_mode = False
                    print(f"[Debug] 状态已清空: transcript={st.session_state.voice_transcript}, processed_id={st.session_state.voice_processed_id}, audio_key={st.session_state.voice_audio_key}")
                    st.rerun()
    
    # 3️⃣ 文件上传控件
    uploaded_files = None
    if SENSE_TOOLS_AVAILABLE:
        st.markdown('<p class="input-label">📎 文件上传 <span class="input-hint">- 支持图片识别、PDF/Word 解析、代码文件</span></p>', unsafe_allow_html=True)
        uploaded_files = st.file_uploader(
            "文件上传",
            accept_multiple_files=True,
            type=['png', 'jpg', 'jpeg', 'pdf', 'docx', 'txt', 'md', 'py', 'js', 'json', 'yaml', 'yml'],
            key=f"record_file_uploader_{st.session_state.file_uploader_key}",
            label_visibility="collapsed"
        )
    
    # 存入按钮
    if st.button("📥 存入 Inbox", type="primary", use_container_width=True):
        has_content = False
        
        # 逻辑 A: 处理文本输入
        if user_input and user_input.strip():
            try:
                print(f"\n⚡ [Record] 保存文本: {user_input[:50]}...")
                fragment_id = add_fragment(user_input.strip())
                
                if fragment_id:
                    print(f"✅ 文本碎片已保存 (ID: {fragment_id})")
                    has_content = True
                else:
                    st.error("❌ 文本保存失败")
                    
            except Exception as e:
                print(f"❌ [Record] 文本保存异常: {str(e)}")
                st.error(f"❌ 文本保存失败: {str(e)}")
        
        # 逻辑 B: 处理附件上传
        if SENSE_TOOLS_AVAILABLE and uploaded_files:
            with st.status("🔍 正在智能分析附件...", expanded=True) as status:
                for idx, uploaded_file in enumerate(uploaded_files, 1):
                    try:
                        st.write(f"📄 正在处理: **{uploaded_file.name}** ({idx}/{len(uploaded_files)})")
                        
                        # 判断文件类型
                        file_type = uploaded_file.type
                        filename = uploaded_file.name
                        
                        # 图片类型
                        if file_type and 'image' in file_type:
                            st.write(f"   🖼️ 识别为图片，调用 Vision API...")
                            parsed_content = process_image(uploaded_file, file_type)
                        else:
                            # 文档类型
                            st.write(f"   📑 识别为文档，提取文本...")
                            parsed_content = process_file(uploaded_file)
                        
                        # 格式化存储
                        formatted_content = f"【附件: {filename}】\n\n{parsed_content}"
                        
                        # 入库
                        fragment_id = add_fragment(formatted_content, source="attachment")
                        
                        if fragment_id:
                            st.write(f"   ✅ 已保存 (ID: {fragment_id})")
                            has_content = True
                        else:
                            st.write(f"   ❌ 保存失败")
                        
                    except Exception as e:
                        st.write(f"   ❌ 处理失败: {str(e)}")
                        print(f"❌ [Record] 附件处理异常: {str(e)}")
                
                # 更新状态
                status.update(label="✅ 处理完成", state="complete")
        
        # 反馈与刷新
        if has_content:
            st.toast("✅ 已成功存入 Inbox！", icon="✅")
            # 重置文本框和文件上传组件（通过更新 key 清空内容）
            st.session_state.text_input_key += 1
            st.session_state.file_uploader_key += 1
            time.sleep(0.5)
            st.rerun()
        elif not user_input.strip() and not uploaded_files:
            st.warning("⚠️ 请输入文本或上传文件")
    
    # 显示使用提示
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div style="text-align: left; border-left: 4px solid #2196F3; padding-left: 12px;">
            <p style="font-size: 16px; font-weight: 600; margin-bottom: 8px; color: #2196F3;">💻 技术笔记</p>
            <div style="background-color: #E3F2FD; padding: 12px; border-radius: 8px; text-align: left;">
                <p style="font-size: 14px; margin: 4px 0; color: #1565C0;">学习 FastAPI 的依赖注入</p>
                <p style="font-size: 14px; margin: 4px 0; color: #1565C0;">Python 3.12 新特性</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div style="text-align: left; border-left: 4px solid #4CAF50; padding-left: 12px;">
            <p style="font-size: 16px; font-weight: 600; margin-bottom: 8px; color: #4CAF50;">✅ 待办事项</p>
            <div style="background-color: #E8F5E9; padding: 12px; border-radius: 8px; text-align: left;">
                <p style="font-size: 14px; margin: 4px 0; color: #2E7D32;">买咖啡豆</p>
                <p style="font-size: 14px; margin: 4px 0; color: #2E7D32;">给老板发周报</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div style="text-align: left; border-left: 4px solid #9C27B0; padding-left: 12px;">
            <p style="font-size: 16px; font-weight: 600; margin-bottom: 8px; color: #9C27B0;">💡 灵感想法</p>
            <div style="background-color: #F3E5F5; padding: 12px; border-radius: 8px; text-align: left;">
                <p style="font-size: 14px; margin: 4px 0; color: #7B1FA2;">做一个 AI 日记助手</p>
                <p style="font-size: 14px; margin: 4px 0; color: #7B1FA2;">写博客分享学习心得</p>
            </div>
        </div>
        """, unsafe_allow_html=True)


# --- Tab 2: Daily Feed ---
if current_tab == "📰 Daily Feed":
    # 调用封装好的 Daily Feed 渲染函数
    render_daily_feed()


# --- Tab 3: Chat (智能问答) ---
if current_tab == "💬 Chat":
    # P1: 确保向量检索可用（初始化客户端）
    if EMBEDDING_AVAILABLE:
        init_embedding_client()

    st.header("💬 智能问答")
    st.caption("和你的第二大脑对话，查询知识库内容")
    
    # 初始化聊天历史
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    
    # 初始化快捷指令触发状态（包含显示文本和完整prompt）
    if "quick_command" not in st.session_state:
        st.session_state.quick_command = None  # {"display": "用户看到的", "prompt": "发给AI的"}
    
    # ===================== 快捷指令区 (Suggestion Chips) =====================
    st.markdown("""
    <style>
    .chip-container {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        margin: 15px 0;
    }
    .chip-btn {
        display: inline-flex;
        align-items: center;
        padding: 10px 20px;
        border-radius: 25px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.3s ease;
        border: none;
        color: white;
        text-decoration: none;
    }
    .chip-random {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        box-shadow: 0 3px 10px rgba(102, 126, 234, 0.3);
    }
    .chip-random:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
    }
    .chip-weekly {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        box-shadow: 0 3px 10px rgba(79, 172, 254, 0.3);
    }
    .chip-weekly:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(79, 172, 254, 0.4);
    }
    .chip-todo {
        background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
        box-shadow: 0 3px 10px rgba(250, 112, 154, 0.3);
    }
    .chip-todo:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(250, 112, 154, 0.4);
    }
    .chip-hotspot {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        box-shadow: 0 3px 10px rgba(17, 153, 142, 0.3);
    }
    .chip-hotspot:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(17, 153, 142, 0.4);
    }
    </style>
    
    <div style="margin-bottom: 10px;">
        <span style="font-size: 16px; font-weight: 600; color: #374151;">✨ 快捷指令</span>
        <span style="font-size: 12px; color: #9ca3af; margin-left: 8px;">点击快速开始对话</span>
    </div>
    """, unsafe_allow_html=True)
    
    # 彩色卡片式快捷指令 - 注入按钮样式
    st.markdown("""
    <style>
    /* 快捷指令按钮悬停效果 */
    div[data-testid="stVerticalBlock"] div[data-testid="stHorizontalBlock"] button {
        transition: all 0.2s ease;
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stHorizontalBlock"] button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    </style>
    """, unsafe_allow_html=True)
    
    chip_col1, chip_col2, chip_col3, chip_col4 = st.columns(4)
    
    with chip_col1:
        with st.container(border=True):
            # 紫色主题
            st.markdown('''
            <div style="height:4px;background:linear-gradient(90deg,#667eea,#764ba2);border-radius:2px;margin:-1rem -1rem 12px -1rem;"></div>
            ''', unsafe_allow_html=True)
            if st.button("🎲 随便看看", key="chip_random", use_container_width=True, type="primary"):
                random_card_json = get_random_card()
                if random_card_json:
                    import json
                    card_data = json.loads(random_card_json)
                    card_title = card_data.get("title", "未知卡片")
                    
                    display_prompt = f"🎲 随便看看：帮我回顾一下「{card_title}」这个知识点"
                    full_prompt = f"""我刚才随机翻到了这张卡片：

```json
{random_card_json}
```

请扮演我的学习教练，帮我回顾一下这个知识点。你可以考考我，或者补充一些我可能忽略的细节。"""
                    st.session_state.quick_command = {"display": display_prompt, "prompt": full_prompt}
                    st.rerun()
                else:
                    st.warning("📭 知识库为空，快去 Record 页面记录一些吧！")
            st.caption("灵感漫游")
    
    with chip_col2:
        with st.container(border=True):
            # 蓝色主题
            st.markdown('''
            <div style="height:4px;background:linear-gradient(90deg,#4facfe,#00f2fe);border-radius:2px;margin:-1rem -1rem 12px -1rem;"></div>
            ''', unsafe_allow_html=True)
            if st.button("📝 生成周报", key="chip_weekly", use_container_width=True, type="primary"):
                recent_cards = get_cards_from_last_days(7)
                if recent_cards:
                    import json
                    cards_summary = json.dumps(recent_cards, ensure_ascii=False, indent=2)
                    
                    display_prompt = f"📝 生成周报：根据过去 7 天的 {len(recent_cards)} 条记录生成开发周报"
                    full_prompt = f"""以下是我过去 7 天的记录（共 {len(recent_cards)} 条）：

```json
{cards_summary}
```

请帮我写一份开发周报。要求：
1. 按类型分组（技术学习、待办完成、灵感想法）
2. 提炼关键成果和进展
3. 列出下周计划"""
                    st.session_state.quick_command = {"display": display_prompt, "prompt": full_prompt}
                    st.rerun()
                else:
                    st.warning("📭 过去 7 天没有记录，快去 Record 页面记录一些吧！")
            st.caption("7天总结")
    
    with chip_col3:
        with st.container(border=True):
            # 粉黄色主题
            st.markdown('''
            <div style="height:4px;background:linear-gradient(90deg,#fa709a,#fee140);border-radius:2px;margin:-1rem -1rem 12px -1rem;"></div>
            ''', unsafe_allow_html=True)
            if st.button("⚡ 待办盘点", key="chip_todo", use_container_width=True, type="primary"):
                display_prompt = "⚡ 待办盘点：查找所有待办事项并按紧急程度排序"
                full_prompt = """请帮我查找所有类型为 todo 的卡片，并按紧急程度排序。

请用清晰的列表格式展示：
1. ❗ 已逾期的任务（最紧急）
2. 🟢 今天截止的任务
3. 🟡 近期即将到期的任务
4. ⚪ 暂无截止日期的任务

如果没有待办事项，请告诉我。"""
                st.session_state.quick_command = {"display": display_prompt, "prompt": full_prompt}
                st.rerun()
            st.caption("任务清单")
    
    with chip_col4:
        with st.container(border=True):
            # 绿色主题
            st.markdown('''
            <div style="height:4px;background:linear-gradient(90deg,#11998e,#38ef7d);border-radius:2px;margin:-1rem -1rem 12px -1rem;"></div>
            ''', unsafe_allow_html=True)
            if st.button("📊 知识热点", key="chip_hotspot", use_container_width=True, type="primary"):
                display_prompt = "📊 知识热点：分析我最近关注的技术领域和高频标签"
                full_prompt = """请分析我最近记录的所有卡片，告诉我：

1. **技术热点**：我最近关注的技术领域是什么？
2. **高频标签**：出现次数最多的 Top 5 标签
3. **知识空白**：有哪些领域只是简单记录了，但还没有深入学习？
4. **建议**：基于我的学习轨迹，推荐接下来应该关注什么"""
                st.session_state.quick_command = {"display": display_prompt, "prompt": full_prompt}
                st.rerun()
            st.caption("趋势分析")
    
    st.divider()
    
    # 显示历史消息
    for idx, message in enumerate(st.session_state.chat_messages):
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                # 助手消息：渲染卡片链接（传入索引以确保 key 唯一）
                render_chat_message_with_card_links(message["content"], message_index=idx)
            else:
                # 用户消息：直接显示
                st.markdown(message["content"])
    
    # 用户输入框（始终显示）
    chat_input_value = st.chat_input("向你的第二大脑提问...")
    
    # 处理快捷指令触发的 Prompt
    user_question = None
    display_message = None  # 用户看到的消息
    
    if st.session_state.quick_command:
        # 快捷指令：分离显示文本和完整 prompt
        display_message = st.session_state.quick_command["display"]
        user_question = st.session_state.quick_command["prompt"]
        st.session_state.quick_command = None  # 清除状态
    elif chat_input_value:
        # 普通输入：显示和发送一致
        user_question = chat_input_value
        display_message = chat_input_value
    
    if user_question:
        # 显示用户消息（显示简洁版本）
        st.session_state.chat_messages.append({"role": "user", "content": display_message})
        with st.chat_message("user"):
            st.markdown(display_message)
        
        # 生成回复
        with st.chat_message("assistant"):
            with st.spinner("🔍 正在检索记忆..."):
                try:
                    # 创建 Knowledge Agent（启用工具调用，已实现完整流程）
                    model_config = get_cached_model_config()
                    knowledge_agent = create_knowledge_agent(model_config, use_tool_calling=True)
                    
                    # 调用 Agent
                    result = run_async(knowledge_agent.invoke({"query": user_question}))
                    
                    # 获取回复
                    response = result.get("output", "").strip()
                    
                    # 防御性检查：确保响应不为空
                    if not response:
                        response = "⚠️ 抱歉，我没有生成有效的回答。请重试或换个问法。"
                        print(f"⚠️ [Chat Debug] Agent 返回空响应: {result}")
                    
                    # 显示回复（带卡片链接，使用当前消息数作为索引）
                    current_msg_index = len(st.session_state.chat_messages)
                    render_chat_message_with_card_links(response, message_index=current_msg_index)
                    
                    # 保存到历史（只保存非空消息）
                    if response:
                        st.session_state.chat_messages.append({"role": "assistant", "content": response})
                    
                except Exception as e:
                    error_msg = f"❌ 抱歉，查询出错：{str(e)}"
                    st.error(error_msg)
                    st.session_state.chat_messages.append({"role": "assistant", "content": error_msg})
    
    # 使用说明
    if not st.session_state.chat_messages:
        st.divider()
        st.markdown("""
        ### 👋 使用指南
        
        你可以这样提问：
        - “有关 Python 的笔记”
        - “FastAPI 的使用方法”
        - “我记录过哪些待办事项？”
        - “关于数据库的知识”
        
        **智能搜索**：Agent 会自动调用工具查找相关卡片。
        """)
    
    # 清空历史按钮
    if st.session_state.chat_messages:
        if st.button("🗑️ 清空聊天记录"):
            st.session_state.chat_messages = []
            st.rerun()


# ===================== Footer =====================

st.divider()
st.caption("🧠 DeepDigest Lite v1.0 | Powered by OpenJiuwen Framework")

# ===================== 自动刷新检查通知 =====================
# 每30秒检查一次新通知
if NOTIFICATIONS_AVAILABLE:
    import time as time_module
    
    # 初始化上次检查时间
    if "last_notification_check" not in st.session_state:
        st.session_state.last_notification_check = time_module.time()
    
    # 检查是否需要刷新
    current_time = time_module.time()
    if current_time - st.session_state.last_notification_check > 30:  # 30秒
        st.session_state.last_notification_check = current_time
        # 检查是否有新通知
        unread = get_notifications(unread_only=True)
        if unread:
            # 有新通知，触发重新加载
            st.rerun()
