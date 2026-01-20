# Automated Environment Setup Agent

## 简介
这是一个基于 **OpenJiuwen** 框架开发的自动化环境构建 Agent。旨在解决 Python 项目开发中最繁琐的环境配置问题。

该 Agent 能够全自动地完成以下流程：
1.  **拉取代码**：从 GitHub 克隆仓库（支持私有仓库 Token）。
2.  **规划环境**：智能分析仓库中的配置文件（`readme.md`, `environment.yml`, `requirements.txt`, `setup.py`, `pyproject.toml` 等），制定最佳的环境安装计划。
3.  **构建环境**：创建 Conda 环境并安装依赖。具备**自我修复（Self-Healing）**能力，遇到安装报错时会自动尝试修复。
4.  **验证环境**：自动生成测试脚本，验证所有核心库是否能成功导入，确保环境真实可用。
5.  **导出结果**：验证通过后，将环境导出为 YAML 文件以供重用。

## 快速开始

### 前置要求
- Python 3.10+
- 已安装 [Conda](https://docs.conda.io/en/latest/) (Anaconda 或 Miniconda)
- 已安装 [git]
- 已安装 `openjiuwen` 框架及相关依赖
- 设置好 LLM 相关的环境变量（如 `API_KEY`, `API_BASE`）

### 安装
确保当前目录下包含以下核心文件：
- `main_agent.py`: 入口文件，编排整个工作流。
- `components.py`: 核心组件实现（执行器、扫描器等）。
- `*_agent.py`: 各个子功能的 Agent 定义。

### 使用方法

1. **设置环境变量**
   在终端中设置大模型 API 密钥：
   ```bash
   # Windows PowerShell
   $env:API_KEY="your_api_key"
   $env:API_BASE="your_api_base"
   $env:MODEL_NAME="deepseek-v3.2-exp"

   # Linux/Mac
   export API_KEY="your_api_key"
   export API_BASE="your_api_base"
   export MODEL_NAME="deepseek-v3.2-exp"
   ```

2. **运行 Agent**
   直接运行 `main_agent.py`。默认情况下，它会使用脚本内部硬编码的测试参数（可以修改 `main` 函数中的参数）。

   ```bash
   python main_agent.py
   ```

3. **自定义输入**
   若要构建其他代码仓环境，可以通过 `invoke` 方法传递参数：

   ```python
   from main_agent import _build_merged_agent

   agent = _build_merged_agent()
   result = await agent.invoke({
       "user_inputs": {
           "repo_url": "https://github.com/username/repo.git",
           "repo_path": "/abs/path/to/local/dir",
           "token": "optional_github_token"
       }
   })
   ```

## 输出示例

Agent 运行结束后，会打印详细的报告：

```text
======================================================================
📋 COMPLETE WORKFLOW RESULTS
======================================================================

[1] CLONE NODE RESULTS:
  Status: ✅ Success

[2] PLANNING NODE RESULTS:
  Environment Name: repo_name_env
  Version: python=3.10
  Args: cd ... && pip install -r requirements.txt

[3] BUILD NODE RESULTS:
  Status: ✅ Success

[4] TEST NODE RESULTS:
  📊 Final Test Report:
    Summary: All primary dependencies installed successfully.
    Passed: 15
    Failed: 0
  ✅ Environment Verification Passed!

[5] SAVE ENVIRONMENT NODE RESULTS:
  Status: ✅ Success
  Export File: .../saved_environments/repo_name_env_17123456.yml

======================================================================
🎯 FINAL CONDA ENVIRONMENT: repo_name_env
======================================================================
```
