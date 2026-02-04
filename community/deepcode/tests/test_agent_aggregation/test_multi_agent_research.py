#!/usr/bin/env python
# coding: utf-8
# Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.

import unittest

from examples.deepcode_agent.agent_flow import MultiAgentResearchFlow


class MultiAgentResearchTest(unittest.IsolatedAsyncioTestCase):

    @unittest.skip("require llm config")
    async def test_agent_aggregation(self):
        agent_flow = MultiAgentResearchFlow()
        agent_flow.initialize_agents()
        await agent_flow.ainvoke()