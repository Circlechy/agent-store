#!/usr/bin/env python
# coding: utf-8
# Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.

from examples.deepcode_agent.agents import BaseAgent


class AgentAggregation:
    def __init__(self, aggregator: BaseAgent, source_agents: list[BaseAgent]):
        self.aggregator = aggregator
        self.source_agents = source_agents

    async def ainvoke(self, inputs, runtime=None):
        results = {}
        for agent in self.source_agents:
            results[agent.name] = agent.ainvoke(inputs, runtime)

        aggregated_results = []
        for agent in self.source_agents:
            result = await results[agent.name]
            aggregated_results.append(f"""# {agent.name}
{str(result)}
""")
        aggregated_results  = '\n'.join(aggregated_results)
        return await self.aggregator.ainvoke({"query": aggregated_results}, runtime)
