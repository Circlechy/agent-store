#!/usr/bin/env python
# coding: utf-8
# Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
import asyncio
import json
import os
import sys

import shutil
# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from examples.deepcode_agent.agent_flow.multi_agent_research import MultiAgentResearchFlow
from examples.deepcode_agent.agents.react_agent import ChatAgent, AgentConfig

async def chat_agent():
    """
    测试ChatAgent类的功能
    """
    print("开始测试ChatAgent...")

    # 使用用户提供的大模型配置
    llm_config = {
        "model_provider": os.getenv("LLM_MODEL_PROVIDER"),
        "api_key": os.getenv("LLM_API_KEY"),
        "api_base": os.getenv("LLM_API_BASE"),
        "model_name": os.getenv("LLM_MODEL_NAME"),
    }

    # 创建AgentConfig实例
    agent_config = AgentConfig(
        name="test_chat_agent",
        llm_config=llm_config,
        system_prompt="你是一个有用的助手，请用简洁的语言回答问题。"
    )

    # 初始化ChatAgent
    chat_agent = ChatAgent(agent_config)

    # 测试问题
    test_query = "请解释一下什么是人工智能？"

    try:
        # 调用ChatAgent的ainvoke方法
        result = await chat_agent.ainvoke({"query": test_query})

        # 打印结果
        print("测试结果：")
        print(f"问题: {test_query}")
        print(f"回答: {result.get('content', '无内容')}")
        print("ChatAgent测试成功！")

    except Exception as e:
        print(f"ChatAgent测试失败，错误信息：{str(e)}")
        import traceback
        traceback.print_exc()

async def try_repo_acquisition_workflow():
    """
    测试 _execute_repo_acquisition_workflow 函数的实际功能
    """
    print("开始测试 _execute_repo_acquisition_workflow...")
    
    # 创建测试目录结构
    test_dir = os.path.join(os.getcwd(), "test_repo_acquisition")
    papers_dir = os.path.join(test_dir, "papers")
    paper_id_dir = os.path.join(papers_dir, "1")
    code_base_dir = os.path.join(paper_id_dir, "code_base")
    
    # 确保目录存在
    os.makedirs(code_base_dir, exist_ok=True)
    
    # 创建测试日志文件
    download_log = os.path.join(paper_id_dir, "repo_acquisition_log.txt")
    open(download_log, "w").close()  # 创建空文件
    
    # 准备测试数据
    reference_data = """
    参考资料包含以下GitHub仓库链接：
    1. https://github.com/python/cpython.git
    2. https://github.com/pandas-dev/pandas.git
    """
    
    dir_info = {
        "download_path": download_log,
        "paper_dir": paper_id_dir
    }
    
    try:
        # 初始化MultiAgentResearchFlow
        marf = MultiAgentResearchFlow()
        # 启用索引功能
        marf.enable_index = True
        # 只初始化需要的代理
        await marf._initialize_github_acquisition_agent()
        
        # 调用要测试的函数
        await marf._execute_repo_acquisition_workflow(
            reference_data=reference_data,
            dir_map=dir_info
        )
        
        # 验证结果
        print("\n测试结果验证：")
        print(f"1. 代码库目录是否存在：{os.path.exists(code_base_dir)}")
        
        # 检查是否有仓库被下载
        if os.path.exists(code_base_dir):
            repos = [d for d in os.listdir(code_base_dir) if os.path.isdir(os.path.join(code_base_dir, d))]
            print(f"2. 下载的仓库数量：{len(repos)}")
            if repos:
                print(f"3. 下载的仓库列表：{repos}")
        
        # 检查日志文件
        print(f"4. 日志文件是否存在：{os.path.exists(download_log)}")
        if os.path.exists(download_log):
            with open(download_log, "r", encoding="utf-8") as f:
                log_content = f.read()
            print(f"5. 日志文件内容长度：{len(log_content)} 字符")
            print(f"6. 日志文件内容前100字符：{log_content[:100]}...")
        
        print("\n_execute_repo_acquisition_workflow 测试完成！")
        
    except Exception as e:
        print(f"\n_execute_repo_acquisition_workflow 测试失败，错误信息：{str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理测试目录
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
            print(f"\n测试目录已清理：{test_dir}")

async def main():
    
    # choice = input("请输入选项（1/2/3）：")
    # 
    # if choice == "1":
    #     await chat_agent()
    # elif choice == "2":
    path = "C:\\Users\\Artillery\\Desktop\\2.pdf"
    marf = MultiAgentResearchFlow()
    await marf.initialize_agents()
    await marf.ainvoke(path)
    # await try_repo_acquisition_workflow()


if __name__ == "__main__":
    asyncio.run(main())