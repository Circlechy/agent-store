"""
DeepDigest Lite - UI 渲染组件 (重构版)
使用 Streamlit 原生组件进行布局，避免 HTML 渲染问题
支持混合召回 (Hybrid Retrieval) 策略
"""

import streamlit as st
import time
from typing import Dict, List, Optional, Set
from datetime import datetime
from src.tools.memory_tools import delete_card_by_id, update_card, find_similar_card_ids


# ===================== 类型映射 =====================

TYPE_ICONS = {
    "tech": "💻",
    "todo": "📋",
    "idea": "💡"
}

TYPE_LABELS = {
    "tech": "技术笔记",
    "todo": "待办事项",
    "idea": "灵感想法"
}


# ===================== 辅助函数 =====================

def get_type_icon(card_type: str) -> str:
    """根据卡片类型返回 Emoji 图标"""
    return TYPE_ICONS.get(card_type, "📝")


def get_type_label(card_type: str) -> str:
    """根据卡片类型返回中文标签"""
    return TYPE_LABELS.get(card_type, "笔记")


def format_datetime(iso_string: str) -> str:
    """格式化 ISO 时间字符串"""
    if not iso_string:
        return ""
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return iso_string[:16] if len(iso_string) > 16 else iso_string


def find_card_title_by_id(card_id: str, all_cards: List[Dict]) -> str:
    """根据卡片 ID 查找标题"""
    if not all_cards:
        return card_id[:8] + "..."
    for card in all_cards:
        if card.get("id") == card_id:
            return card.get("title", card_id[:8] + "...")
    return card_id[:8] + "..."


def format_deadline_status(deadline_str: str) -> tuple:
    """格式化截止日期状态
    
    Args:
        deadline_str: 截止日期字符串，格式 "YYYY-MM-DD"
    
    Returns:
        tuple: (状态文本, 状态颜色) 例如 ("🔴 已逾期 3 天", "error")
    """
    if not deadline_str:
        return None, None
    
    try:
        deadline = datetime.fromisoformat(deadline_str).date()
        today = datetime.now().date()
        delta = (deadline - today).days
        
        if delta < 0:
            # 已逾期
            return f"🔴 已逾期 {abs(delta)} 天", "error"
        elif delta == 0:
            # 今天截止
            return "🟢 今天截止", "success"
        elif delta == 1:
            # 明天
            return "🟡 明天", "warning"
        elif delta <= 7:
            # 一周内
            return f"{delta} 天后 ({deadline_str})", "info"
        else:
            # 较远的日期
            return f"{deadline_str}", "normal"
    except:
        return f"{deadline_str}", "normal"


# ===================== 主渲染函数 =====================

def render_card(card: Dict, all_cards: Optional[List[Dict]] = None, context: str = "main"):
    """
    渲染单张知识卡片（使用 Streamlit 原生组件）
    支持删除/完成功能
    
    Args:
        card: 卡片数据字典
        all_cards: 所有卡片列表（用于查找关联卡片的标题）
        context: 渲染上下文标识，用于区分不同位置的相同卡片（避免 key 冲突）
    """
    card_type = card.get("type", "tech")
    icon = get_type_icon(card_type)
    type_label = get_type_label(card_type)
    
    title = card.get("title", "无标题")
    tags = card.get("tags", [])
    summary = card.get("summary", "")
    snippet = card.get("snippet", {})
    related_ids = card.get("related_card_ids", [])
    created_at = card.get("created_at", "")
    card_id = card.get("id", "")
    
    # 根据卡片类型定义柔和的颜色主题
    TYPE_COLORS = {
        "tech": {"bg": "#E3F2FD", "border": "#64B5F6", "accent": "#1976D2"},      # 柔和蓝色
        "todo": {"bg": "#E8F5E9", "border": "#81C784", "accent": "#388E3C"},      # 柔和绿色
        "idea": {"bg": "#F3E5F5", "border": "#BA68C8", "accent": "#7B1FA2"},      # 柔和紫色
        "note": {"bg": "#FFF8E1", "border": "#FFD54F", "accent": "#F57C00"}       # 柔和橙色
    }
    colors = TYPE_COLORS.get(card_type, TYPE_COLORS["note"])
    
    # 使用带边框的容器作为卡片，并添加顶部颜色条
    with st.container(border=True):
        # 顶部颜色装饰条
        st.markdown(f"""
        <div style="
            height: 4px; 
            background: linear-gradient(90deg, {colors['border']} 0%, {colors['accent']} 100%);
            margin: -1rem -1rem 0.75rem -1rem;
            border-radius: 4px 4px 0 0;
        "></div>
        """, unsafe_allow_html=True)
        # === 第一行：图标 + 标题 + 类型标签 + 操作按钮 ===
        col_icon, col_title, col_type, col_button = st.columns([0.5, 6, 2, 1.5])
        
        with col_icon:
            st.markdown(f"### {icon}")
        
        with col_title:
            st.subheader(title, anchor=False)
            
            # 如果是待办事项且有截止日期，显示动态状态
            if card_type == "todo":
                deadline = card.get("deadline")
                if deadline:
                    status_text, status_type = format_deadline_status(deadline)
                    if status_text:
                        if status_type == "error":
                            st.error(status_text, icon="⏰")
                        elif status_type == "success":
                            st.success(status_text, icon="⏰")
                        elif status_type == "warning":
                            st.warning(status_text, icon="⏰")
                        else:
                            st.info(status_text, icon="📅")
        
        with col_type:
            # 使用不同颜色的标签
            if card_type == "tech":
                st.markdown(f":blue-background[{type_label}]")
            elif card_type == "todo":
                st.markdown(f":green-background[{type_label}]")
            elif card_type == "idea":
                st.markdown(f":violet-background[{type_label}]")
            else:
                st.caption(type_label)
        
        with col_button:
            # 编辑和删除按钮
            btn_col1, btn_col2 = st.columns(2)
            
            with btn_col1:
                # 编辑按钮
                if st.button("✏️", key=f"{context}_edit_{card_id}", help="编辑卡片"):
                    st.session_state[f"editing_{card_id}"] = True
                    st.rerun()
            
            with btn_col2:
                # 根据卡片类型显示不同的删除按钮
                if card_type == "todo":
                    button_label = "✅"
                    toast_message = "任务已完成！"
                else:
                    button_label = "🗑️"
                    toast_message = "卡片已删除"
                
                # 点击按钮删除卡片
                if st.button(button_label, key=f"{context}_btn_{card_id}", help="删除卡片"):
                    success = delete_card_by_id(card_id)
                    if success:
                        st.toast(toast_message, icon="✅")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.toast("❌ 操作失败", icon="❌")
        
        # === 编辑模式 ===
        if st.session_state.get(f"editing_{card_id}", False):
            st.divider()
            st.subheader("✏️ 编辑卡片")
            
            # 编辑表单
            with st.form(key=f"{context}_edit_form_{card_id}"):
                new_title = st.text_input("标题", value=title)
                new_tags_str = st.text_input("标签（用逗号分隔）", value=", ".join(tags))
                new_summary = st.text_area("摘要", value=summary, height=100)
                new_type = st.selectbox("类型", ["tech", "todo", "idea"], index=["tech", "todo", "idea"].index(card_type))
                
                # 待办事项的截止日期（仅 todo 类型显示）
                new_deadline = None
                if new_type == "todo":
                    current_deadline = card.get("deadline", "")
                    new_deadline = st.date_input(
                        "截止日期（可选）", 
                        value=datetime.fromisoformat(current_deadline).date() if current_deadline else None,
                        help="留空表示无截止日期"
                    )
                
                # 代码片段编辑 - 支持 code 模式和 before/after 模式
                st.caption("代码片段（可选）")
                
                # 检测当前 snippet 模式
                has_before_after = snippet.get("before") or snippet.get("after")
                has_single_code = snippet.get("code") and not has_before_after
                
                # 根据现有格式选择编辑模式
                snippet_mode = st.radio(
                    "代码格式",
                    ["单一代码", "Before/After 对比"],
                    index=0 if has_single_code or not has_before_after else 1,
                    horizontal=True,
                    key=f"{context}_snippet_mode_{card_id}"
                )
                
                if snippet_mode == "单一代码":
                    new_code = st.text_area(
                        "代码", 
                        value=snippet.get("code", ""), 
                        height=150,
                        key=f"{context}_code_{card_id}"
                    )
                    new_before = ""
                    new_after = ""
                else:
                    new_code = ""
                    col_b, col_a = st.columns(2)
                    with col_b:
                        new_before = st.text_area(
                            "❌ Before（修改前）", 
                            value=snippet.get("before", ""), 
                            height=150,
                            key=f"{context}_before_{card_id}"
                        )
                    with col_a:
                        new_after = st.text_area(
                            "✅ After（修改后）", 
                            value=snippet.get("after", ""), 
                            height=150,
                            key=f"{context}_after_{card_id}"
                        )
                
                new_language = st.text_input("语言", value=snippet.get("language", "python"))
                
                col1, col2 = st.columns(2)
                with col1:
                    submit = st.form_submit_button("💾 保存", use_container_width=True, type="primary")
                with col2:
                    cancel = st.form_submit_button("❌ 取消", use_container_width=True)
                
                if submit:
                    # 构建更新数据
                    updates = {
                        "title": new_title,
                        "tags": [tag.strip() for tag in new_tags_str.split(",") if tag.strip()],
                        "summary": new_summary,
                        "type": new_type
                    }
                    
                    # 更新截止日期（仅 todo 类型）
                    if new_type == "todo" and new_deadline:
                        updates["deadline"] = new_deadline.strftime("%Y-%m-%d")
                    elif new_type == "todo" and not new_deadline:
                        updates["deadline"] = None
                    
                    # 更新代码片段（根据模式选择格式）
                    if snippet_mode == "单一代码" and new_code:
                        updates["snippet"] = {
                            "code": new_code,
                            "language": new_language
                        }
                    elif snippet_mode == "Before/After 对比" and (new_before or new_after):
                        updates["snippet"] = {
                            "before": new_before,
                            "after": new_after,
                            "language": new_language
                        }
                    
                    # 执行更新
                    success = update_card(card_id, updates)
                    if success:
                        st.toast("✅ 更新成功！", icon="✅")
                        st.session_state[f"editing_{card_id}"] = False
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.toast("❌ 更新失败", icon="❌")
                
                if cancel:
                    st.session_state[f"editing_{card_id}"] = False
                    st.rerun()
            
            st.divider()
        
        # === 标签展示 ===
        if tags and not st.session_state.get(f"editing_{card_id}", False):
            tags_str = " ".join([f"`#{tag}`" for tag in tags])
            st.markdown(tags_str)
        
        # === 第二行：摘要内容（根据类型显示不同颜色）===
        if summary:
            # 使用 HTML 渲染带颜色的摘要框
            st.markdown(f"""
            <div style="
                background-color: {colors['bg']};
                border-left: 3px solid {colors['border']};
                padding: 12px 16px;
                border-radius: 0 8px 8px 0;
                margin: 8px 0;
                color: #333;
            ">
                <span style="margin-right: 8px;">📄</span>{summary}
            </div>
            """, unsafe_allow_html=True)
        
        # === 第三行：代码片段（如果有）===
        if snippet and (snippet.get("code") or snippet.get("before") or snippet.get("after")):
            with st.expander("📄 查看代码", expanded=False):
                # 检查是否有 before/after 对比
                before_code = snippet.get("before", "")
                after_code = snippet.get("after", "")
                single_code = snippet.get("code", "")
                language = snippet.get("language", "python")
                
                if before_code or after_code:
                    # Before/After 对比模式
                    col_before, col_after = st.columns(2)
                    with col_before:
                        st.caption("❌ Before")
                        st.code(before_code or "// 无", language=language)
                    with col_after:
                        st.caption("✅ After")
                        st.code(after_code or "// 无", language=language)
                elif single_code:
                    # 单一代码模式
                    st.code(single_code, language=language)
        
        # === 第四行：底部信息 ===
        st.divider()
        
        col_time, col_relation = st.columns([1, 1])
        
        with col_time:
            time_str = format_datetime(created_at)
            if time_str:
                st.caption(f"� {time_str}")
            if card_id:
                st.caption(f"🆔 {card_id[:8]}...")
        
        with col_relation:
            # === 知识链 (Knowledge Chain) - 混合召回 ===
            # 路 A: 逻辑关联 (LLM 生成的 related_card_ids)
            logic_related_ids: Set[str] = set(related_ids) if related_ids else set()
            
            # 路 B: 语义关联 (Embedding 相似度)
            semantic_related_ids: Set[str] = set()
            if card_id:
                try:
                    similar_ids = find_similar_card_ids(card_id, top_k=3)
                    semantic_related_ids = set(similar_ids)
                except Exception as e:
                    print(f"⚠️ 语义关联查询失败: {e}")
            
            # 合并去重，排除自己
            all_related_ids = (logic_related_ids | semantic_related_ids) - {card_id}
            
            # 渲染知识链
            if all_related_ids and all_cards:
                with st.expander("🔗 相关卡片链接", expanded=False):
                    for rid in all_related_ids:
                        # 查找卡片信息
                        related_card = next((c for c in all_cards if c.get("id") == rid), None)
                        
                        if related_card:
                            rel_title = related_card.get("title", rid[:8] + "...")
                            rel_type = related_card.get("type", "tech")
                            rel_icon = get_type_icon(rel_type)
                            
                            # 使用与测试按钮完全相同的跳转逻辑
                            button_text = f"{rel_icon} {rel_title[:40]}{'...' if len(rel_title) > 40 else ''}"
                            button_key = f"jump_{context}_{card_id[:8]}_{rid[:8]}"
                            
                            if st.button(
                                button_text,
                                key=button_key,
                                use_container_width=True,
                                type="secondary"
                            ):
                                st.session_state.active_tab = "📰 Daily Feed"
                                st.session_state.card_search_query = rid[:8]
                                st.session_state._jumping_to_card = True
                                st.rerun()
                        else:
                            # 卡片不存在，仅显示 ID
                            st.caption(f"• {rid[:8]}... (卡片已删除)")


def render_empty_state(message: str = "暂无内容", icon: str = "📭"):
    """渲染空状态"""
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"<h1 style='text-align: center;'>{icon}</h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; color: gray;'>{message}</p>", unsafe_allow_html=True)
    st.markdown("---")


def render_inbox_counter(count: int):
    """渲染 Inbox 计数器"""
    if count > 0:
        st.metric(
            label="📥 Inbox 待处理",
            value=count,
            delta=f"{count} 条碎片等待整理",
            delta_color="normal"
        )
    else:
        st.metric(
            label="📥 Inbox",
            value=0,
            delta="已清空 ✨",
            delta_color="off"
        )


def render_stats_row(cards_count: int, fragments_count: int):
    """渲染统计信息行"""
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📚 知识卡片", cards_count)
    with col2:
        st.metric("📥 待处理碎片", fragments_count)


# ===================== CSS 样式注入 =====================

def inject_css():
    """
    注入自定义 CSS 样式
    为不同类型的卡片设置柔和的背景色和优化的视觉效果
    """
    st.markdown("""
    <style>
    /* 全局字体大小统一 */
    html, body, [class*="css"] {
        font-size: 14px;
    }
    
    /* 侧边栏样式 */
    [data-testid="stSidebar"] {
        font-size: 14px;
    }
    
    [data-testid="stSidebar"] .stMarkdown p {
        font-size: 14px;
        line-height: 1.5;
    }
    
    [data-testid="stSidebar"] h1 {
        font-size: 1.5rem !important;
    }
    
    [data-testid="stSidebar"] h2 {
        font-size: 1.1rem !important;
    }
    
    [data-testid="stSidebar"] h3 {
        font-size: 1rem !important;
    }
    
    /* 侧边栏 metric 样式 */
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stMetricLabel"] {
        font-size: 0.85rem !important;
    }
    
    /* 主区域标题 */
    .main h1 {
        font-size: 1.75rem !important;
    }
    
    .main h2 {
        font-size: 1.4rem !important;
    }
    
    .main h3 {
        font-size: 1.15rem !important;
    }
    
    .main h4 {
        font-size: 1rem !important;
    }
    
    /* 正文和段落 */
    .main p, .main span, .main div {
        font-size: 14px;
        line-height: 1.6;
    }
    
    /* 按钮文字 */
    button {
        font-size: 14px !important;
    }
    
    /* 输入框 */
    input, textarea, select {
        font-size: 14px !important;
    }
    
    /* 卡片容器样式优化 */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px;
        transition: all 0.2s ease;
        border: 1px solid #e0e0e0;
    }
    
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
        transform: translateY(-2px);
    }
    
    /* 标签样式优化 */
    code {
        background-color: rgba(0, 0, 0, 0.05) !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
        font-size: 0.85em !important;
    }
    
    /* 分割线样式 */
    hr {
        margin: 0.75rem 0 !important;
        border-color: rgba(0, 0, 0, 0.08) !important;
    }
    
    /* 按钮悬停效果 */
    button[kind="secondary"]:hover {
        transform: scale(1.05);
    }
    
    /* caption 样式 */
    .stCaption, [data-testid="stCaptionContainer"] {
        font-size: 0.85rem !important;
        color: #666 !important;
    }
    
    /* expander 标题 */
    [data-testid="stExpander"] summary {
        font-size: 14px !important;
    }
    
    /* pills/tabs 导航 */
    [data-testid="stPills"] button {
        font-size: 14px !important;
    }
    
    /* ===================== Tabs 分类标签样式 ===================== */
    /* Tabs 容器 */
    [data-testid="stTabs"] {
        margin-bottom: 1rem;
    }
    
    /* Tabs 按钮 - 增大字体和点击区域 */
    [data-testid="stTabs"] button {
        font-size: 1rem !important;
        font-weight: 500 !important;
        padding: 0.6rem 1.2rem !important;
        min-height: 44px !important;
    }
    
    /* Tabs 按钮文字 */
    [data-testid="stTabs"] button p {
        font-size: 1rem !important;
        font-weight: 500 !important;
    }
    
    /* 选中状态的 Tab */
    [data-testid="stTabs"] button[aria-selected="true"] {
        font-weight: 600 !important;
    }
    
    /* ===================== 代码块样式 ===================== */
    /* 代码块容器 - 增大字体 */
    [data-testid="stCode"], pre, .stCodeBlock {
        font-size: 0.95rem !important;
        line-height: 1.6 !important;
    }
    
    /* 代码块内部文字 */
    [data-testid="stCode"] code,
    pre code,
    .stCodeBlock code {
        font-size: 0.95rem !important;
        line-height: 1.6 !important;
        font-family: 'Consolas', 'Monaco', 'Courier New', monospace !important;
    }
    
    /* Expander 内的代码块 */
    [data-testid="stExpander"] [data-testid="stCode"] code,
    [data-testid="stExpander"] pre code {
        font-size: 0.9rem !important;
        line-height: 1.5 !important;
    }
    
    /* toast 消息 */
    [data-testid="stToast"] {
        font-size: 14px !important;
    }
    
    /* 对话框标题 */
    [data-testid="stModal"] h1, [data-testid="stModal"] h2 {
        font-size: 1.3rem !important;
    }
    
    /* 表单标签 */
    .stTextInput label, .stTextArea label, .stSelectbox label, .stDateInput label {
        font-size: 14px !important;
    }
    
    /* ===================== Primary 按钮美化 ===================== */
    /* 所有 primary 按钮基础样式 */
    button[kind="primary"] {
        border-radius: 20px !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15) !important;
    }
    
    button[kind="primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2) !important;
    }
    
    /* Secondary 按钮美化 */
    button[kind="secondary"] {
        border-radius: 15px !important;
        transition: all 0.2s ease !important;
    }
    
    button[kind="secondary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
    }
    
    /* ===================== 聊天消息美化 ===================== */
    /* 用户消息气泡 */
    [data-testid="stChatMessage"][data-testid*="user"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border-radius: 18px 18px 4px 18px !important;
    }
    
    /* 助手消息气泡 */
    [data-testid="stChatMessage"]:not([data-testid*="user"]) {
        background: #f8f9fa !important;
        border-radius: 18px 18px 18px 4px !important;
        border: 1px solid #e9ecef !important;
    }
    </style>
    """, unsafe_allow_html=True)
