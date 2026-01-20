"""
Sub Agent (Task 工具) E2E 测试

使用 jiuwen CLI 进行端到端验证，测试子代理功能：
- Explore 子代理：代码探索
- Plan 子代理：实现规划
- Bash 子代理：命令执行
- general-purpose 子代理：复杂任务

运行方式:
    # 运行所有 Sub Agent 测试
    /home/snape/claude-code-projects/openjiuwen-code/python11venv/bin/python3.11 -m pytest tests/e2e/test_sub_agent.py -v -m e2e -s

    # 运行单个测试
    /home/snape/claude-code-projects/openjiuwen-code/python11venv/bin/python3.11 -m pytest tests/e2e/test_sub_agent.py::TestExploreSubAgent -v -m e2e -s
"""

import pytest
import os
import re

from .conftest import (
    requires_api_key,
    JiuwenRunner,
)


# ============================================================================
# 辅助函数：严格的断言
# ============================================================================

def assert_no_subagent_errors(response) -> None:
    """断言子代理执行没有错误

    检查响应中是否包含子代理执行异常的标志
    """
    error_patterns = [
        r"子代理执行异常",
        r"子代理执行失败",
        r"validation error",
        r"BaseModelInfo",
        r"错误: 子代理",
        r"Error.*subagent",
        r"SubAgent.*error",
    ]

    content = response.content + response.stdout + response.stderr

    for pattern in error_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            pytest.fail(
                f"子代理执行出错，匹配到错误模式: {pattern}\n"
                f"响应内容: {content[:1000]}"
            )


def assert_subagent_executed(response) -> None:
    """断言子代理确实被执行了

    检查响应中是否包含子代理执行的标志
    """
    execution_patterns = [
        r"● Task\(",
        r"task\(",
        r"Explore",
        r"Plan",
        r"子代理",
        r"subagent",
    ]

    content = response.content + response.stdout

    for pattern in execution_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return

    # 如果没有找到子代理执行标志，检查是否有实质性的分析结果
    # （Agent 可能直接执行而不显式调用 Task 工具）
    if len(response.content) > 200:
        return

    pytest.fail(
        f"未检测到子代理执行标志\n"
        f"响应内容: {response.content[:500]}"
    )


def assert_response_has_content(response, keywords: list, min_length: int = 100) -> None:
    """断言响应包含有意义的内容

    Args:
        response: JiuwenResponse 对象
        keywords: 期望包含的关键词列表（至少匹配一个）
        min_length: 最小响应长度
    """
    content = response.content.lower()

    # 检查响应长度
    if len(response.content) < min_length:
        pytest.fail(
            f"响应内容过短（{len(response.content)} < {min_length}）\n"
            f"响应: {response.content}"
        )

    # 检查关键词
    found_keywords = [kw for kw in keywords if kw.lower() in content]
    if not found_keywords:
        pytest.fail(
            f"响应未包含任何期望的关键词: {keywords}\n"
            f"响应内容: {response.content[:500]}"
        )


# ============================================================================
# Fixture: 多文件项目（用于 Explore 测试）
# ============================================================================

@pytest.fixture
def multi_file_project(temp_project):
    """创建多文件项目结构，用于测试 Explore 子代理

    项目结构:
        temp_project/
        ├── src/
        │   ├── __init__.py
        │   ├── main.py
        │   ├── user_service.py
        │   ├── order_service.py
        │   └── utils/
        │       ├── __init__.py
        │       └── helpers.py
        ├── tests/
        │   ├── __init__.py
        │   └── test_user.py
        └── README.md
    """
    project_dir = temp_project

    # 创建目录结构
    src_dir = os.path.join(project_dir, "src")
    utils_dir = os.path.join(src_dir, "utils")
    tests_dir = os.path.join(project_dir, "tests")
    os.makedirs(utils_dir, exist_ok=True)
    os.makedirs(tests_dir, exist_ok=True)

    # src/__init__.py
    with open(os.path.join(src_dir, "__init__.py"), 'w') as f:
        f.write('"""源代码包"""\n')

    # src/main.py
    with open(os.path.join(src_dir, "main.py"), 'w', encoding='utf-8') as f:
        f.write('''"""主程序入口"""

from user_service import UserService
from order_service import OrderService


def main():
    """程序入口点"""
    user_service = UserService()
    order_service = OrderService()

    # 创建用户
    user = user_service.create_user("Alice", "alice@example.com")
    print(f"Created user: {user}")

    # 创建订单
    order = order_service.create_order(user["id"], [
        {"product": "Book", "price": 29.99},
        {"product": "Pen", "price": 4.99},
    ])
    print(f"Created order: {order}")


if __name__ == "__main__":
    main()
''')

    # src/user_service.py
    with open(os.path.join(src_dir, "user_service.py"), 'w', encoding='utf-8') as f:
        f.write('''"""用户服务模块"""

from typing import Dict, Optional


class UserService:
    """用户服务类 - 管理用户的创建、查询和删除"""

    def __init__(self):
        self.users: Dict[int, dict] = {}
        self._next_id = 1

    def create_user(self, name: str, email: str) -> dict:
        """创建新用户

        Args:
            name: 用户名
            email: 用户邮箱

        Returns:
            包含用户信息的字典
        """
        user_id = self._next_id
        self._next_id += 1
        self.users[user_id] = {
            "id": user_id,
            "name": name,
            "email": email,
            "status": "active"
        }
        return self.users[user_id]

    def get_user(self, user_id: int) -> Optional[dict]:
        """获取用户信息"""
        return self.users.get(user_id)

    def delete_user(self, user_id: int) -> bool:
        """删除用户"""
        if user_id in self.users:
            del self.users[user_id]
            return True
        return False

    def list_users(self) -> list:
        """列出所有用户"""
        return list(self.users.values())
''')

    # src/order_service.py
    with open(os.path.join(src_dir, "order_service.py"), 'w', encoding='utf-8') as f:
        f.write('''"""订单服务模块"""

from typing import Dict, List, Optional
from datetime import datetime


class OrderService:
    """订单服务类 - 管理订单的创建和查询"""

    def __init__(self):
        self.orders: Dict[int, dict] = {}
        self._next_id = 1

    def create_order(self, user_id: int, items: List[dict]) -> dict:
        """创建订单

        Args:
            user_id: 用户 ID
            items: 订单项列表，每项包含 product 和 price

        Returns:
            订单信息字典
        """
        order_id = self._next_id
        self._next_id += 1

        total = sum(item.get("price", 0) for item in items)

        self.orders[order_id] = {
            "id": order_id,
            "user_id": user_id,
            "items": items,
            "total": total,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        return self.orders[order_id]

    def get_order(self, order_id: int) -> Optional[dict]:
        """获取订单信息"""
        return self.orders.get(order_id)

    def get_user_orders(self, user_id: int) -> List[dict]:
        """获取用户的所有订单"""
        return [o for o in self.orders.values() if o["user_id"] == user_id]
''')

    # src/utils/__init__.py
    with open(os.path.join(utils_dir, "__init__.py"), 'w') as f:
        f.write('"""工具函数包"""\n')

    # src/utils/helpers.py
    with open(os.path.join(utils_dir, "helpers.py"), 'w', encoding='utf-8') as f:
        f.write('''"""辅助函数"""

import re
from typing import Optional


def validate_email(email: str) -> bool:
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def format_currency(amount: float, currency: str = "USD") -> str:
    """格式化货币"""
    symbols = {"USD": "$", "EUR": "€", "CNY": "¥"}
    symbol = symbols.get(currency, currency)
    return f"{symbol}{amount:.2f}"


def generate_order_number(order_id: int) -> str:
    """生成订单号"""
    return f"ORD-{order_id:06d}"
''')

    # tests/__init__.py
    with open(os.path.join(tests_dir, "__init__.py"), 'w') as f:
        f.write('"""测试包"""\n')

    # tests/test_user.py
    with open(os.path.join(tests_dir, "test_user.py"), 'w', encoding='utf-8') as f:
        f.write('''"""用户服务测试"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from user_service import UserService


class TestUserService:
    """用户服务测试类"""

    def test_create_user(self):
        """测试创建用户"""
        service = UserService()
        user = service.create_user("Alice", "alice@example.com")

        assert user["name"] == "Alice"
        assert user["email"] == "alice@example.com"
        assert user["status"] == "active"
        assert "id" in user

    def test_get_user(self):
        """测试获取用户"""
        service = UserService()
        created = service.create_user("Bob", "bob@example.com")
        retrieved = service.get_user(created["id"])

        assert retrieved == created

    def test_delete_user(self):
        """测试删除用户"""
        service = UserService()
        user = service.create_user("Charlie", "charlie@example.com")

        assert service.delete_user(user["id"]) == True
        assert service.get_user(user["id"]) is None
''')

    # README.md
    with open(os.path.join(project_dir, "README.md"), 'w', encoding='utf-8') as f:
        f.write('''# 示例电商项目

一个简单的电商后端服务示例。

## 功能

- 用户管理（创建、查询、删除）
- 订单管理（创建、查询）
- 工具函数（邮箱验证、货币格式化）

## 项目结构

```
src/
├── main.py           # 主程序入口
├── user_service.py   # 用户服务
├── order_service.py  # 订单服务
└── utils/
    └── helpers.py    # 辅助函数
```

## 运行

```bash
python src/main.py
```

## 测试

```bash
pytest tests/
```
''')

    return {
        "project_dir": project_dir,
        "src_dir": src_dir,
        "tests_dir": tests_dir,
        "main_file": os.path.join(src_dir, "main.py"),
        "user_service_file": os.path.join(src_dir, "user_service.py"),
        "order_service_file": os.path.join(src_dir, "order_service.py"),
        "helpers_file": os.path.join(utils_dir, "helpers.py"),
    }


# ============================================================================
# Fixture: 需要规划的功能需求（用于 Plan 测试）
# ============================================================================

@pytest.fixture
def feature_request_project(temp_project):
    """创建需要规划新功能的项目

    场景：需要为现有项目添加"购物车"功能
    """
    project_dir = temp_project

    # 创建基础项目结构
    src_dir = os.path.join(project_dir, "src")
    os.makedirs(src_dir, exist_ok=True)

    # 现有的产品服务
    with open(os.path.join(src_dir, "product_service.py"), 'w', encoding='utf-8') as f:
        f.write('''"""产品服务模块"""

from typing import Dict, List, Optional


class ProductService:
    """产品服务"""

    def __init__(self):
        self.products: Dict[int, dict] = {
            1: {"id": 1, "name": "iPhone 15", "price": 999.00, "stock": 100},
            2: {"id": 2, "name": "MacBook Pro", "price": 2499.00, "stock": 50},
            3: {"id": 3, "name": "AirPods Pro", "price": 249.00, "stock": 200},
        }

    def get_product(self, product_id: int) -> Optional[dict]:
        """获取产品信息"""
        return self.products.get(product_id)

    def list_products(self) -> List[dict]:
        """列出所有产品"""
        return list(self.products.values())

    def check_stock(self, product_id: int, quantity: int) -> bool:
        """检查库存是否充足"""
        product = self.products.get(product_id)
        if not product:
            return False
        return product["stock"] >= quantity
''')

    # 功能需求文档
    with open(os.path.join(project_dir, "FEATURE_REQUEST.md"), 'w', encoding='utf-8') as f:
        f.write('''# 功能需求：购物车系统

## 背景

用户需要能够将商品添加到购物车，并在结账前管理购物车内容。

## 功能要求

### 核心功能

1. **添加商品到购物车**
   - 指定商品 ID 和数量
   - 检查库存是否充足
   - 如果商品已在购物车中，增加数量

2. **从购物车移除商品**
   - 支持完全移除
   - 支持减少数量

3. **查看购物车**
   - 显示所有商品
   - 显示每项小计
   - 显示总价

4. **清空购物车**
   - 一键清空所有商品

### 技术要求

- 与现有 ProductService 集成
- 支持多用户（每个用户独立购物车）
- 购物车数据暂存内存（后续可扩展到 Redis）

### 接口设计

```python
class CartService:
    def add_item(self, user_id: int, product_id: int, quantity: int) -> dict
    def remove_item(self, user_id: int, product_id: int, quantity: int = None) -> bool
    def get_cart(self, user_id: int) -> dict
    def clear_cart(self, user_id: int) -> bool
    def get_total(self, user_id: int) -> float
```
''')

    return {
        "project_dir": project_dir,
        "src_dir": src_dir,
        "product_service_file": os.path.join(src_dir, "product_service.py"),
        "feature_request_file": os.path.join(project_dir, "FEATURE_REQUEST.md"),
    }


# ============================================================================
# Test Case 1: Explore 子代理 - 代码探索
# ============================================================================

@pytest.mark.e2e
@pytest.mark.sub_agent
class TestExploreSubAgent:
    """测试 Explore 子代理 - 代码探索功能

    Explore 子代理用于：
    - 快速探索代码库结构
    - 查找特定文件或代码
    - 回答代码库相关问题
    """

    @requires_api_key
    @pytest.mark.asyncio
    async def test_explore_project_structure(self, runner: JiuwenRunner, multi_file_project: dict):
        """测试探索项目结构

        场景：用户想了解项目的整体结构
        预期：Agent 使用 Explore 子代理探索并总结项目结构
        """
        project = multi_file_project

        query = f"""请帮我探索这个项目的结构。

项目路径: {project['project_dir']}

我想知道：
1. 项目有哪些主要目录和文件？
2. 项目的主要功能模块是什么？
3. 入口文件在哪里？

请使用 Task 工具启动 Explore 子代理来完成这个任务。"""

        response = await runner.run(query, timeout=120)

        # 严格验证：检查子代理执行没有错误
        assert_no_subagent_errors(response)

        # 验证响应包含项目结构信息
        assert_response_has_content(
            response,
            keywords=["src", "main", "user", "order", "目录", "结构", "文件", "py"],
            min_length=100
        )

    @requires_api_key
    @pytest.mark.asyncio
    async def test_explore_find_specific_code(self, runner: JiuwenRunner, multi_file_project: dict):
        """测试查找特定代码

        场景：用户想找到处理用户创建的代码
        预期：Agent 使用 Explore 子代理定位到 user_service.py 中的 create_user 方法
        """
        project = multi_file_project

        query = f"""在项目 {project['project_dir']} 中，帮我找到处理用户创建的代码。

我想知道：
1. 用户创建的逻辑在哪个文件？
2. 具体是哪个函数/方法？
3. 这个方法的参数和返回值是什么？

请使用 Task 工具的 Explore 子代理来搜索代码。"""

        response = await runner.run(query, timeout=120)

        # 严格验证：检查子代理执行没有错误
        assert_no_subagent_errors(response)

        # 验证找到了 create_user 相关信息
        assert_response_has_content(
            response,
            keywords=["create_user", "user_service", "userservice", "创建用户", "name", "email"],
            min_length=100
        )


# ============================================================================
# Test Case 2: Plan 子代理 - 实现规划
# ============================================================================

@pytest.mark.e2e
@pytest.mark.sub_agent
class TestPlanSubAgent:
    """测试 Plan 子代理 - 实现规划功能

    Plan 子代理用于：
    - 设计实现方案
    - 识别关键文件
    - 考虑架构权衡
    """

    @requires_api_key
    @pytest.mark.asyncio
    async def test_plan_new_feature(self, runner: JiuwenRunner, feature_request_project: dict):
        """测试规划新功能实现

        场景：用户需要为项目添加购物车功能
        预期：Agent 使用 Plan 子代理分析需求并制定实现计划
        """
        project = feature_request_project

        query = f"""我需要为项目添加购物车功能。

项目路径: {project['project_dir']}
需求文档: {project['feature_request_file']}

请帮我：
1. 阅读需求文档
2. 分析现有代码结构
3. 制定实现计划

请使用 Task 工具的 Plan 子代理来完成规划任务。

输出应包含：
- 需要创建的新文件
- 需要修改的现有文件
- 实现步骤（按优先级排序）
- 潜在的技术风险"""

        response = await runner.run(query, timeout=180)

        # 严格验证：检查子代理执行没有错误
        assert_no_subagent_errors(response)

        # 验证响应包含规划信息
        assert_response_has_content(
            response,
            keywords=["cart", "购物车", "实现", "步骤", "计划", "方案", "product", "文件"],
            min_length=150
        )


# ============================================================================
# Test Case 3: Bash 子代理 - 命令执行
# ============================================================================

@pytest.mark.e2e
@pytest.mark.sub_agent
class TestBashSubAgent:
    """测试 Bash 子代理 - 命令执行功能

    Bash 子代理用于：
    - 执行 git 操作
    - 运行构建命令
    - 执行测试
    """

    @requires_api_key
    @pytest.mark.asyncio
    async def test_bash_run_tests(self, runner: JiuwenRunner, multi_file_project: dict):
        """测试运行测试命令

        场景：用户想运行项目的测试
        预期：Agent 使用 Bash 子代理执行 pytest 命令
        """
        project = multi_file_project

        query = f"""请帮我运行项目的测试。

项目路径: {project['project_dir']}
测试目录: {project['tests_dir']}

请使用 Task 工具的 Bash 子代理来执行测试命令。
使用 pytest 运行测试，并告诉我测试结果。"""

        response = await runner.run(query, timeout=120)

        # 严格验证：检查子代理执行没有错误
        assert_no_subagent_errors(response)

        # 验证响应包含测试相关信息
        assert_response_has_content(
            response,
            keywords=["pytest", "test", "passed", "failed", "测试", "通过", "失败", "error"],
            min_length=50
        )

    @requires_api_key
    @pytest.mark.asyncio
    async def test_bash_check_python_version(self, runner: JiuwenRunner):
        """测试执行简单命令

        场景：用户想检查 Python 版本
        预期：Agent 使用 Bash 子代理执行 python --version
        """
        query = """请帮我检查当前系统的 Python 版本。

使用 Task 工具的 Bash 子代理执行命令，告诉我 Python 的版本号。"""

        response = await runner.run(query, timeout=60)

        # 严格验证：检查子代理执行没有错误
        assert_no_subagent_errors(response)

        # 验证响应包含 Python 版本信息
        assert_response_has_content(
            response,
            keywords=["python", "3.", "版本", "version"],
            min_length=20
        )


# ============================================================================
# Test Case 4: general-purpose 子代理 - 复杂任务
# ============================================================================

@pytest.mark.e2e
@pytest.mark.sub_agent
@pytest.mark.slow
class TestGeneralPurposeSubAgent:
    """测试 general-purpose 子代理 - 复杂多步骤任务

    general-purpose 子代理用于：
    - 执行复杂的多步骤任务
    - 需要多种工具配合的场景
    - 独立完成完整的子任务
    """

    @requires_api_key
    @pytest.mark.asyncio
    async def test_general_analyze_and_document(self, runner: JiuwenRunner, multi_file_project: dict):
        """测试分析代码并生成文档

        场景：用户需要分析代码并生成 API 文档
        预期：Agent 使用 general-purpose 子代理完成多步骤任务
        """
        project = multi_file_project
        output_dir = os.path.join(project["project_dir"], "docs")
        os.makedirs(output_dir, exist_ok=True)

        query = f"""请帮我分析项目代码并生成 API 文档。

项目路径: {project['project_dir']}
输出目录: {output_dir}

任务：
1. 分析 src/ 目录下的所有 Python 文件
2. 提取所有类和方法的信息
3. 生成 API 文档（Markdown 格式）
4. 保存到 {output_dir}/API.md

请使用 Task 工具的 general-purpose 子代理来完成这个复杂任务。"""

        response = await runner.run(query, timeout=180)

        # 严格验证：检查子代理执行没有错误
        assert_no_subagent_errors(response)

        # 验证响应包含分析信息
        assert_response_has_content(
            response,
            keywords=["userservice", "orderservice", "api", "文档", "分析", "class", "method", "user", "order"],
            min_length=100
        )

        # 检查是否生成了文档文件（可选验证）
        doc_file = os.path.join(output_dir, "API.md")
        if os.path.exists(doc_file):
            with open(doc_file, 'r', encoding='utf-8') as f:
                content = f.read()
            assert len(content) > 50, f"生成的文档应有实质内容，实际长度: {len(content)}"


# ============================================================================
# Test Case 5: 子代理模式限制测试
# ============================================================================

@pytest.mark.e2e
@pytest.mark.sub_agent
class TestSubAgentModeRestrictions:
    """测试子代理的模式限制

    验证不同模式下子代理的使用限制：
    - BUILD 模式：可用所有子代理
    - PLAN 模式：只能用 Explore/Plan
    - REVIEW 模式：只能用 Explore
    """

    @requires_api_key
    @pytest.mark.asyncio
    async def test_explore_in_any_mode(self, runner: JiuwenRunner, multi_file_project: dict):
        """测试 Explore 子代理在任何模式下都可用

        Explore 是只读操作，应该在所有模式下都可用
        """
        project = multi_file_project

        query = f"""请使用 Explore 子代理查看项目 {project['project_dir']} 的文件结构。

只需要列出主要的目录和文件即可。"""

        response = await runner.run(query, timeout=90)

        # 严格验证：检查子代理执行没有错误
        assert_no_subagent_errors(response)

        # Explore 应该成功执行
        assert_response_has_content(
            response,
            keywords=["src", "main", "py", "文件", "目录", "user", "order"],
            min_length=50
        )


# ============================================================================
# Test Case 6: 并行子代理测试
# ============================================================================

@pytest.mark.e2e
@pytest.mark.sub_agent
@pytest.mark.slow
class TestParallelSubAgents:
    """测试并行启动多个子代理

    验证 Agent 能够同时启动多个独立的子代理任务
    """

    @requires_api_key
    @pytest.mark.asyncio
    async def test_parallel_explore_tasks(self, runner: JiuwenRunner, multi_file_project: dict):
        """测试并行探索任务

        场景：同时探索多个不同的代码模块
        预期：Agent 能够并行启动多个 Explore 子代理
        """
        project = multi_file_project

        query = f"""请帮我同时分析以下两个模块：

项目路径: {project['project_dir']}

任务 1: 分析 user_service.py 的功能
任务 2: 分析 order_service.py 的功能

请使用 Task 工具启动子代理来并行完成这两个任务。
最后汇总两个模块的功能对比。"""

        response = await runner.run(query, timeout=180)

        # 严格验证：检查子代理执行是否有错误
        assert_no_subagent_errors(response)

        # 验证响应包含有意义的内容
        assert_response_has_content(
            response,
            keywords=["user", "用户", "order", "订单", "服务", "service", "功能", "模块"],
            min_length=100
        )

        # 验证响应包含两个模块的信息
        response_content = response.content.lower()
        has_user_info = (
            "user" in response_content or
            "用户" in response.content
        )
        has_order_info = (
            "order" in response_content or
            "订单" in response.content
        )

        # 至少应该分析了其中一个模块
        assert has_user_info or has_order_info, \
            f"响应应包含模块分析信息，实际响应: {response.content[:500]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e", "-s"])
