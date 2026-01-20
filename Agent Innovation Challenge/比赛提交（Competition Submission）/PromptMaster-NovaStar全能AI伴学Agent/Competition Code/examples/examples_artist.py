"""Star-Artist 使用示例（仅故事生成）。"""

import asyncio
import os
import sys
import io

# 设置输出编码为UTF-8（Windows系统需要）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from novastar.agents import StarArtist
from novastar.nodes import ArtistNode
from novastar.utils.config import get_config


def get_llm_config_from_env() -> dict:
    """从环境变量和配置文件获取LLM配置."""
    config = get_config()
    api_key = config.get_env("openai_api_key")
    api_base = config.get_env("openai_api_base")
    model_type = config.get_env("llm_model_type") or "openai"
    model_name = config.get_env("llm_model_name") or "qwen-plus"
    
    if not api_key:
        return None
    
    return {
        "model_type": model_type,
        "model_name": model_name,
        "api_key": api_key,
        "api_base": api_base,
        "timeout": 60,
    }


def create_artist_with_llm():
    """创建带LLM配置的StarArtist实例."""
    llm_config = get_llm_config_from_env()
    if llm_config:
        return StarArtist(name="Star-Artist", llm_config=llm_config)
    else:
        return StarArtist(name="Star-Artist")


async def example_generate_story():
    """故事生成示例（包含多模态内容：文本、图片、语音）."""
    print("\n" + "=" * 60)
    print("示例1: 故事生成（多模态）")
    print("=" * 60)

    artist = StarArtist(name="Star-Artist", auto_load_llm=False)

    result = await artist.generate_story(
        user_id="child_001",
        request="一个关于勇气和友谊的冒险故事",
        context={
            "age": 6,
            "interests": ["冒险", "友谊", "恐龙"],
        },
    )

    print(f"描述：{result['description']}")
    content = result.get("content", {})
    if not isinstance(content, dict):
        print(f"内容：{content}")
        return

    print(f"标题：{content.get('title', 'N/A')}")

    paragraphs = content.get("paragraphs", [])
    if paragraphs:
        print(f"\n前三段：")
        for para in paragraphs[:3]:
            print(f"\n  段落 {para.get('index', 'N/A')}:")
            para_text = para.get("text", "")
            print(f"    文本：{para_text[:80]}..." if len(para_text) > 80 else f"    文本：{para_text}")
            print(f"    图片：{para.get('image', 'N/A')[:80]}...")
            audio_data = para.get('audio', 'N/A')
            if isinstance(audio_data, str) and audio_data.startswith('data:audio'):
                audio_info = f"base64 data URI ({len(audio_data)} 字符)" if len(audio_data) > 80 else audio_data[:80]
                print(f"    语音：{audio_info}")
            else:
                print(f"    语音：{str(audio_data)[:80]}...")

    metadata = result.get("metadata", {})
    if metadata:
        print(f"\n元数据：")
        print(f"  年龄组：{metadata.get('age_group', 'N/A')}")
        print(f"  预计时长：{metadata.get('duration_minutes', 'N/A')} 分钟")
        print(f"  段落数量：{metadata.get('paragraph_count', 'N/A')}")


async def example_using_node_directly():
    """直接使用底层节点示例."""
    print("\n" + "=" * 60)
    print("示例2: 直接使用底层ArtistNode")
    print("=" * 60)

    # 创建节点
    artist_node = ArtistNode(config={})

    # 模拟输入
    inputs = {
        "query": "讲一个关于月亮和兔子的温馨故事",
        "user_id": "child_002",
        "context": {"age": 5, "interests": ["兔子", "月亮"]},
    }

    # 调用节点
    result = await artist_node._do_invoke(inputs, None, None)

    print(f"查询：{inputs['query']}")
    print(f"内容类型：{result.get('content_type', 'unknown')}")
    print(f"响应：{result.get('response', 'N/A')}")


async def example_with_llm_config():
    """配置LLM的示例."""
    print("\n" + "=" * 60)
    print("示例3: 配置LLM（需要API Key）")
    print("=" * 60)

    # 从环境变量和配置文件获取LLM配置
    llm_config = get_llm_config_from_env()

    if not llm_config:
        print("未设置OPENAI_API_KEY，跳过此示例")
        print("请在 .env 文件中设置 OPENAI_API_KEY 和 OPENAI_API_BASE")
        return

    artist = StarArtist(
        name="Star-Artist",
        llm_config=llm_config,
    )

    result = await artist.generate_story(
        user_id="child_001",
        request="一个关于勇气和友谊的冒险故事",
        context={
            "age": 8,
            "interests": ["冒险", "友谊"],
        },
    )

    print(f"描述：{result['description']}")
    content = result.get("content", {})
    if isinstance(content, dict):
        print(f"标题：{content.get('title', 'N/A')}")
        text = content.get("text", "")
        text_preview = text[:200] + "..." if len(text) > 200 else text
        print(f"内容预览：\n{text_preview}")
        
        paragraphs = content.get("paragraphs", [])
        if paragraphs:
            print(f"\n多模态段落数：{len(paragraphs)}")
            print(f"首个段落预览：")
            first_para = paragraphs[0]
            print(f"  文本：{first_para.get('text', '')[:100]}...")
            print(f"  图片：{first_para.get('image', '')[:60]}...")
            
            # 音频现在是 base64 data URI 格式
            audio_data = first_para.get('audio', '')
            if audio_data.startswith('data:audio'):
                print(f"  语音：base64 data URI 格式 ({len(audio_data)} 字符)")
                print(f"       可以直接在浏览器中播放")
            else:
                print(f"  语音：{audio_data[:60]}...")


async def main():
    """运行所有示例."""
    print("\n" + "=" * 60)
    print("Star-Artist 使用示例")
    print("基于openjiuwen框架构建")
    print("=" * 60 + "\n")

    await example_generate_story()
    await example_using_node_directly()
    await example_with_llm_config()

    print("\n" + "=" * 60)
    print("示例运行完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
