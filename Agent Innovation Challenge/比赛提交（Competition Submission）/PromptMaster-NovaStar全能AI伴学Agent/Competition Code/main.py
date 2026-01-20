"""NovaStar主入口文件.

基于openjiuwen框架构建的儿童AI伴学Agent系统。

使用方法:
    python main.py "你好，我想学习恐龙的知识"
    python main.py --user_id child_001 "给我讲个故事"
    python main.py --mode interactive
"""

import argparse
import asyncio
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from novastar.workflow.novastar_workflow import NovaStarWorkflow, create_novastar_workflow
from novastar.utils.config import get_config, load_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_llm_config() -> dict:
    """从配置文件和环境变量获取LLM配置.

    Returns:
        LLM配置字典
    """
    config = get_config()

    # 从配置读取API密钥
    api_key = config.get_env("openai_api_key")
    api_base = config.get_env("openai_api_base")

    # 模型配置
    model_type = config.get_env("llm_model_type") or "openai"
    model_name = config.get_env("llm_model_name") or "gpt-4o-mini"

    return {
        "model_type": model_type,
        "model_name": model_name,
        "api_key": api_key,
        "api_base": api_base,
        "timeout": 60,
        "image_model_name": config.get_env("image_model_name") or None,
        "tts_model_name": config.get_env("tts_model_name") or None,
        "asr_model_name": config.get_env("asr_model_name") or None,
    }


def get_agent_config() -> dict:
    """从配置文件获取Agent配置.

    Returns:
        Agent配置字典
    """
    config = get_config()

    return {
        "commander": config.get_commander_config(),
        "mentor": config.get_mentor_config(),
        "artist": config.get_artist_config(),
    }


async def run_single_query(
    workflow: NovaStarWorkflow,
    query: str,
    user_id: str,
    context: Optional[dict] = None,
) -> None:
    """运行单次查询.

    Args:
        workflow: NovaStar工作流实例
        query: 用户查询
        user_id: 用户ID
        context: 上下文
    """
    logger.info(f"处理查询: {query}")

    conversation_id = str(uuid.uuid4())

    try:
        # 流式输出
        final_response = ""
        async for chunk in workflow.run(
            query=query,
            user_id=user_id,
            conversation_id=conversation_id,
            context=context,
        ):
            if "response" in chunk and chunk["response"]:
                final_response = chunk["response"]
            if "content" in chunk and chunk["content"]:
                # 实时输出内容
                print(chunk["content"], end="", flush=True)

        if final_response and not chunk.get("content"):
            print(f"\n\n🌟 Novy: {final_response}")
        else:
            print()  # 换行

        logger.info(f"查询处理完成: conversation_id={conversation_id}")

    except Exception as e:
        logger.error(f"查询处理失败: {e}")
        print(f"\n❌ 抱歉，处理请求时遇到问题: {e}")


async def run_interactive_mode(workflow: NovaStarWorkflow, user_id: str) -> None:
    """运行交互模式.

    Args:
        workflow: NovaStar工作流实例
        user_id: 用户ID
    """
    print("\n" + "=" * 60)
    print("🌟 欢迎使用 NovaStar - 启明星儿童AI伴学系统 🌟")
    print("=" * 60)
    print("\n你好！我是Novy，你的AI学习伙伴！")
    print("你可以问我任何问题，或者让我给你讲故事、玩游戏。")
    print("输入 'quit' 或 'exit' 退出对话。\n")

    context = {"age": 6}  # 默认年龄

    while True:
        try:
            # 获取用户输入
            user_input = input("👦 你: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "退出", "再见"]:
                print("\n🌟 Novy: 再见！希望很快能再见到你！记得好好学习、天天向上哦！")
                break

            # 处理设置年龄命令
            if user_input.startswith("/age "):
                try:
                    age = int(user_input.split()[1])
                    if 3 <= age <= 12:
                        context["age"] = age
                        print(f"\n🌟 Novy: 好的，我记住了！你{age}岁，我会根据你的年龄调整内容哦！\n")
                    else:
                        print("\n🌟 Novy: 年龄需要在3-12岁之间哦！\n")
                except ValueError:
                    print("\n🌟 Novy: 请输入正确的年龄数字，比如 /age 6\n")
                continue

            # 处理帮助命令
            if user_input.lower() in ["/help", "帮助", "?"]:
                print("\n🌟 Novy: 我可以帮你做很多事情：")
                print("  📚 回答问题 - 比如「为什么天空是蓝色的？」")
                print("  📖 讲故事 - 比如「给我讲个恐龙的故事」")
                print("  🎮 玩游戏 - 比如「我们来玩个游戏吧」")
                print("  🎨 画画 - 比如「帮我画个小兔子」")
                print("  💬 聊天 - 比如「我今天很开心」")
                print("\n  /age 6 - 设置年龄")
                print("  /help - 显示帮助")
                print("  quit - 退出对话\n")
                continue

            # 处理用户查询
            print("\n🌟 Novy: ", end="", flush=True)

            async for chunk in workflow.run(
                query=user_input,
                user_id=user_id,
                context=context,
            ):
                if "response" in chunk and chunk["response"]:
                    print(chunk["response"])
                    break
                elif "content" in chunk and chunk["content"]:
                    print(chunk["content"], end="", flush=True)

            print()  # 换行

        except KeyboardInterrupt:
            print("\n\n🌟 Novy: 再见！下次再聊！")
            break
        except Exception as e:
            logger.error(f"处理输入时出错: {e}")
            print(f"\n❌ 抱歉，我遇到了一些问题: {e}\n")


async def main():
    """主函数."""
    parser = argparse.ArgumentParser(
        description="NovaStar - 启明星儿童AI伴学系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py "为什么天空是蓝色的？"
  python main.py --user_id child_001 "给我讲个故事"
  python main.py --mode interactive
  python main.py --age 8 "帮我解释一下光合作用"
        """,
    )

    parser.add_argument(
        "query",
        nargs="*",
        default=[],
        help="用户查询内容",
    )
    parser.add_argument(
        "--mode",
        choices=["query", "interactive"],
        default="query",
        help="运行模式: query(单次查询) 或 interactive(交互模式)",
    )
    parser.add_argument(
        "--user_id",
        type=str,
        default="default_user",
        help="用户ID",
    )
    parser.add_argument(
        "--age",
        type=int,
        default=6,
        help="用户年龄 (3-12岁)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式",
    )

    args = parser.parse_args()

    # 设置日志级别
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # 加载配置
    load_config()

    # 获取配置
    llm_config = get_llm_config()
    agent_config = get_agent_config()

    # 检查API密钥
    if not llm_config.get("api_key"):
        logger.warning("未配置API密钥，将使用模拟响应模式")
        print("\n⚠️ 注意: 未配置OPENAI_API_KEY，系统将使用模拟响应模式。")
        print("请设置环境变量 OPENAI_API_KEY 以启用完整功能。\n")

    # 创建工作流
    logger.info("初始化NovaStar工作流...")
    workflow = create_novastar_workflow(
        llm_config=llm_config,
        agent_config=agent_config,
    )

    # 运行
    if args.mode == "interactive":
        await run_interactive_mode(workflow, args.user_id)
    else:
        if not args.query:
            parser.print_help()
            print("\n请提供查询内容，或使用 --mode interactive 进入交互模式。")
            return

        query = " ".join(args.query)
        context = {"age": args.age}
        await run_single_query(workflow, query, args.user_id, context)


if __name__ == "__main__":
    asyncio.run(main())
