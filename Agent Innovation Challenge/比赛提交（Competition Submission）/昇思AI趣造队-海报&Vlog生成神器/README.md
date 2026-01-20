# 时光映画社 - 海报&Vlog生成神器

## 1. 作品简介

### 场景概述

「时光映画社」是一款基于[**openJiuwen Studio**](https://gitcode.com/openJiuwen/agent-studio)为普通人量身打造的多模态创意创作助手，让“一张海报”、“一段Vlog”的完整内容创作不再依赖专业技能。它打破传统工具的单模态局限，打通图片（贺卡/海报）与视频（Vlog）的全链路生成，还能自动匹配背景音乐、添加精致字幕与专属水印。无论是节日里想给亲友定制“专属贺卡”，旅行中想快速产出“旅行大片”，还是为生活记录制作“日常片段”，都能通过它实现风格统一、内容连贯的高质量输出——让每一份创意都有画面，每一段时光都能被生动定格。

### 功能介绍

详细的功能和使用介绍请看视频：[项目作品创意点介绍、功能与效果展示](./海报&Vlog生成神器Demo.mp4)

### 典型用户场景

> 以下均通过作品Agent进行生成。

1. **节日氛围创作**：春节想给家人送专属祝福，生成新中式、剪纸风格的贺卡，海报还带有“九问”专属水印，社交分享更有仪式感。

<div style="display: flex; justify-content: center; align-items: center; width: 100%; min-height: 300px;">
  <img src="./assets/spring_festival_greeting_card.png"
       alt="春节贺卡"
       style="width: 200px; height: auto;">
</div>

2. **个性化礼品制作**：朋友生日想送独特礼物，给喜爱摄影，又喜爱小动物的TA定制专属祝福海报，心意满满又有创意。

<div style="display: flex; justify-content: center; align-items: center; width: 100%; min-height: 300px;">
  <img src="./assets/birthday_card.png"
       alt="生日贺卡"
       style="width: 200px; height: auto;">
</div>

3. **旅行 Vlog 创作**：来一场说走就走的旅行，用 Agent 生成多帧旅行纪实 Vlog，从 “准备旅行” 到 “旅途归来” 前后画面连贯不割裂，定格旅途美好瞬间。

<div style="display: flex; justify-content: center; align-items: center; width: 100%; min-height: 300px;">
  <img src="./assets/travel_vlog.gif"
       alt="旅行vlog"
       style="width: 200px; height: auto;">
</div>

4. **幻想故事制作**：未来世界的独居生活是怎样的？输入构思文本，用 Agent 生成多帧科幻故事 Vlog，自动匹配赛博感背景音乐与剧情字幕，让文字里的未来独居场景活起来。

<div style="display: flex; justify-content: center; align-items: center; width: 100%; min-height: 300px;">
  <img src="./assets/cyberpunk_life.gif"
       alt="赛博朋克未来生活"
       style="width: 200px; height: auto;">
</div>

## 2. Agent技术方案

### 整体架构

```text
┌─────────────────────────────────────────────┐
│               用户交互层                     │
│ (Agent 对话界面 / 输入框)                    │
└───────────────────┬─────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐
│              Agent 协调层                    │
│・对话管理 (Dialogue Management)              │
│・需求澄清 (Clarify Missing Info)             │
└───────────────────┬─────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐
│              任务规划与执行层                │
│ ┌───────────────┐       ┌───────────────┐   │
│ │ 图片生成工作流 │       │ 视频生成工作流 │   │
│ │(poster_card_  │       │(vlog-         │   │
│ │ generator)    │       │generator)     │   │
│ └───────────────┘       └───────────────┘   │
└─────────────────────────────────────────────┘
```

### 核心技术组件

#### 2.1 多模态生成能力

突破 openJiuwen 平台仅支持单一模态生成的限制，实现贺卡 / 海报（图片）与 Vlog（视频）的多模态联动生成，同时完成音视频多元结合，让生成内容从静态视觉延伸至动态视听体验。

#### 2.2 内容一致性保障模块

针对视频生成中前后帧画面易脱节的问题，从风格、色调、核心元素等维度保障视频前后帧图片生成的一致性，确保视频内容连贯统一。

#### 2.3 专属水印与个性化定制组件

为海报 / 贺卡生成环节添加 “九问” 独特水印，既强化内容专属标识，又满足不同场景下的视觉审美需求。

#### 2.4 工程化适配与问题规避方案

开发过程中针对实际落地的技术痛点，包括但不限于：
- 大模型节点不支持多模态生成
- 代码运行节点前端 timeout 时长过低
- 代码插件 timeout 时长无法设置且过低
- 子工作流文件大小压缩失效
- database 文件存储容量受限

通过工作流拆分、自定义构建代码插件、轻量化文件压缩策略等方式完成适配与规避，保障 Agent 稳定运行；在此特别感谢 @cyz95 在技术答疑与问题解决上提供的专业解答和支持。

## 3. 未来优化方向

1. **生成效果升级**：深化多帧画面一致性优化，提升不同场景下的细节质感与画面连贯性；新增视频 “九问” 专属水印功能，同步优化水印位置与透明度，确保视频与海报水印风格统一，强化内容专属标识。

2. **多模态交互体验增强**：拓展图文混合输入、参考图上传等自然交互方式，支持基于用户提供的图片定制化生成贺卡 / 视频；实现贺卡与短视频的双向联动（如海报元素自动植入视频开篇、视频关键帧提取生成衍生海报），丰富创作链路的关联性与实用性。

## 4. 比赛开发期间反馈Issue

### Feature Request

- [Code nodes support displaying print and logging outputs](https://gitcode.com/openJiuwen/agent-studio/issues/176)
- [Increase Workflow File Size Limit to Support Complex Pipelines](https://gitcode.com/openJiuwen/agent-studio/issues/191)
- [Support Multimodal LLM Nodes for Image, Video, and Audio](https://gitcode.com/openJiuwen/agent-studio/issues/192)
- [Support Multiple Outputs and Rich Data Types in LLM Nodes](https://gitcode.com/openJiuwen/agent-studio/issues/193)
- [Support Common IDE Editing Shortcuts (Tab, Ctrl+Z, etc.)](https://gitcode.com/openJiuwen/agent-studio/issues/194)
- [ Support Multi-Node Deletion via Box Selection in Workflow Editor](https://gitcode.com/openJiuwen/agent-studio/issues/196)
- [Support Passing Previous Iteration Output as Input in Loop Nodes](https://gitcode.com/openJiuwen/agent-studio/issues/200)

### Bug Report

- [Inconsistent Array Input Serialization in Start Node During Test Runs](https://gitcode.com/openJiuwen/agent-studio/issues/195)
- [Sub-Workflow Insertion Increases Workflow File Size Instead of Reducing It](https://gitcode.com/openJiuwen/agent-studio/issues/202)


### Docs

- [Add Usage Documentation and Examples for Supported Nodes](https://gitcode.com/openJiuwen/docs/issues/75)
- [Lack of Clear Contribution and Extension Development Guidelines](https://gitcode.com/openJiuwen/docs/issues/74)

### Experimence Feedback

- [The execution timeout for code nodes in the agent workflow is insufficient.](https://gitcode.com/openJiuwen/agent-studio/issues/173)
- [Agent Fails to Recognize Imported Workflow After Context Deletion](https://gitcode.com/openJiuwen/agent-studio/issues/199)
- [Undo Action Fails to Restore Previous Workflow State in Frontend](https://gitcode.com/openJiuwen/agent-studio/issues/203)