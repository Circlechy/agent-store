"""
DeepDigest API 服务
轻量级 FastAPI 服务，用于接收浏览器插件的信息采集

功能：
1. 提供 /capture 接口，接收网页内容投喂
2. 配置 CORS，允许浏览器插件跨域调用
3. 将采集内容存入 Inbox 数据库
"""

import sys
from pathlib import Path

# 设置项目路径以支持相对导入
DEEP_DIGEST_ROOT = Path(__file__).parent.parent.parent
PROJECT_ROOT = DEEP_DIGEST_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(DEEP_DIGEST_ROOT) not in sys.path:
    sys.path.insert(0, str(DEEP_DIGEST_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# 导入 inbox 工具
from src.tools.inbox_tools import add_fragment, init_inbox_db

# ===================== 数据模型 =====================

class CaptureRequest(BaseModel):
    """网页采集请求数据模型"""
    text: str                    # 选中的文字内容
    url: Optional[str] = ""      # 当前网页 URL
    title: Optional[str] = ""    # 网页标题


class CaptureResponse(BaseModel):
    """采集响应数据模型"""
    success: bool
    message: str
    fragment_id: Optional[int] = None


# ===================== FastAPI 应用 =====================

app = FastAPI(
    title="DeepDigest Capture API",
    description="🧠 DeepDigest 浏览器采集接口 - 让知识触手可及",
    version="1.0.0"
)

# ===================== CORS 配置 =====================
# 必须允许所有来源，否则浏览器插件无法调用本地接口
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],           # 允许所有 HTTP 方法
    allow_headers=["*"],           # 允许所有请求头
)


# ===================== API 路由 =====================

@app.on_event("startup")
async def startup_event():
    """服务启动时初始化数据库"""
    init_inbox_db()
    print("🚀 DeepDigest Capture API 已启动")
    print("📡 等待浏览器投喂...")


@app.get("/")
async def root():
    """健康检查接口"""
    return {
        "status": "alive",
        "service": "DeepDigest Capture API",
        "message": "🧠 准备好接收知识投喂了！"
    }


@app.post("/capture", response_model=CaptureResponse)
async def capture_content(request: CaptureRequest):
    """
    捕获网页内容并存入数据库
    
    接收浏览器插件发送的选中文字，格式化后存入 Inbox。
    
    Args:
        request: 包含 text, url, title 的请求数据
    
    Returns:
        CaptureResponse: 包含保存结果的响应
    """
    # 验证输入
    if not request.text or not request.text.strip():
        raise HTTPException(
            status_code=400,
            detail="捕获内容不能为空"
        )
    
    # 格式化内容
    formatted_content = f"""【来自网页采集】
标题: {request.title or '无标题'}
链接: {request.url or '无链接'}
内容: {request.text.strip()}"""
    
    # 调用 inbox 工具保存碎片
    fragment_id = add_fragment(
        content=formatted_content,
        source="web_capture"  # 标记来源为网页采集
    )
    
    if fragment_id:
        return CaptureResponse(
            success=True,
            message=f"✅ 已捕获并保存 (ID: {fragment_id})",
            fragment_id=fragment_id
        )
    else:
        raise HTTPException(
            status_code=500,
            detail="保存失败，请检查数据库连接"
        )


@app.get("/health")
async def health_check():
    """健康检查接口（供监控使用）"""
    return {"status": "healthy"}


# ===================== 启动入口 =====================

def run_api_server(host: str = "127.0.0.1", port: int = 8787):
    """
    启动 API 服务
    
    Args:
        host: 监听地址，默认 127.0.0.1（仅本地访问）
        port: 监听端口，默认 8787
    """
    import uvicorn
    
    print("=" * 50)
    print("🧠 DeepDigest Capture API")
    print("=" * 50)
    print(f"📡 服务地址: http://{host}:{port}")
    print(f"📖 API 文档: http://{host}:{port}/docs")
    print(f"🔗 采集接口: POST http://{host}:{port}/capture")
    print("=" * 50)
    
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_api_server()
