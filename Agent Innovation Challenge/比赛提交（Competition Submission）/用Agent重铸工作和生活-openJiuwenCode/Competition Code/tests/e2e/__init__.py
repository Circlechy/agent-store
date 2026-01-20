"""
端到端测试 (E2E Tests)

这些测试通过 JiuwenCodeAgent 调用真实的 LLM 来验证完整的用户场景。
需要配置有效的 API Key 才能运行。

运行方式:
    pytest tests/e2e/ -v -m e2e

注意:
    - 这些测试会消耗 API 配额
    - 测试时间较长（每个测试可能需要 10-60 秒）
    - 需要网络连接
"""
