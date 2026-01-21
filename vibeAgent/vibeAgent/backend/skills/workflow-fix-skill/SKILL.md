---
name: workflow-fix-skill
description: 工作流代码修复和分析技能。用于修复工作流代码错误、分析修改需求、确定需要修改的文件。必须严格遵守 openJiuwen WorkflowAgent 框架规范。支持工作流修改分析，通过修改工作流拓扑结构来满足需求，而不是在 component 文件中添加普通函数。
---

# 工作流修复技能

## 概述

本技能提供工作流代码修复和分析的专业指导，确保修复后的代码符合 openJiuwen WorkflowAgent 框架规范。支持两种主要场景：

1. **错误修复**：修复工作流代码中的错误（语法错误、运行时错误等）
2. **需求修改**：分析修改需求，生成新的工作流结构，通过修改拓扑来满足需求

## 核心原则

### 1. 框架规范优先
- **必须严格遵守** openJiuwen WorkflowAgent 框架规范
- 修复时必须参考 `references/framework-rules.md` 中的详细规则
- 不能违反框架的任何强制性约束

### 2. 工作流拓扑优先（修改场景）
- **必须通过修改工作流拓扑结构来满足需求**，而不是在 component 文件中添加普通函数
- **如果需求是增加新功能，应该添加新的组件节点，然后重新连接拓扑**
- **如果需求是修改现有功能，应该修改对应组件的描述和配置**

### 3. 最小化修改
- 只修改必要的代码，保持其他部分不变
- 避免不必要的重构
- 保持代码风格一致性

### 4. 完整性检查
- 确保所有组件都已正确注册
- 确保所有连接都已正确建立
- 确保所有必需的导入都已添加

## 修复流程

### 场景 1: 错误修复

#### 1. 错误分析
- 仔细分析错误信息，定位问题根源
- 检查是否符合框架规范
- 识别需要修改的文件和位置

#### 2. 修复计划
- 制定详细的修复计划
- 确定修改范围和影响
- 确保修复后符合框架规范

#### 3. 执行修复
- 按照修复计划执行修改
- 保持代码风格一致
- 确保所有修改都符合框架规范

### 场景 2: 需求修改

#### 1. 需求分析
- 仔细分析所有需求（历史需求 + 当前需求）
- 理解整体目标
- 查看现有工作流结构

#### 2. 生成新的工作流结构
- 参考 `references/workflow-modification-guide.md` 的指南
- 生成新的 `components` 列表（包含所有组件，包括保留的和新增的）
- 生成新的 `workflow_structure`（包含完整的拓扑连接）

#### 3. 确定修改文件
- 通常包括 `components.py` 和 `workflow_builder.py`
- 为每个文件提供修改说明

#### 4. 执行修改
- 修改 `components.py`：根据新的 `components` 列表添加或修改组件创建函数
- 修改 `workflow_builder.py`：根据新的 `workflow_structure` 重新构建拓扑连接
- **严禁**在 `components.py` 中添加普通辅助函数

## 关键约束

1. **必须使用 openJiuwen 的 Workflow 类**，不要自定义实现
2. **组件必须实现 ComponentExecutable 接口**
3. **必须遵守组件注册和连接规则**
4. **必须遵守输入输出变量命名规则**
5. **修改场景必须通过工作流拓扑来满足需求**，禁止添加普通函数

## 修改场景特殊要求

### 分析阶段
- 必须生成新的 `components` 和 `workflow_structure`
- 参考 `workflow-modification-guide.md` 的指南
- 确保生成的结构符合框架规范
- **必须保留现有组件**：如果现有组件仍然需要，必须在新的 `components` 列表中保留它们

### 文件修改阶段
- **workflow_builder.py**：必须根据新的 `workflow_structure` 重新构建拓扑
- **components.py**：必须根据新的 `components` 列表添加或修改组件创建函数
- **严禁**在 `components.py` 中添加普通辅助函数（如 `format_recommendations_as_letter`）

## 参考文档

详见 `references/` 目录下的文档：
- `framework-rules.md`：openJiuwen WorkflowAgent 框架关键规范（必须严格遵守）
- `workflow-modification-guide.md`：工作流修改完整指南（包含需求分析、新结构生成和文件修改的完整流程）
