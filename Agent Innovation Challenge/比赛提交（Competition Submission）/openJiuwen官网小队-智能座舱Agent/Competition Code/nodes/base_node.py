from openjiuwen.core.component.base import WorkflowComponent
from openjiuwen.core.component.branch_router import BranchRouter
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.graph.executable import Input, Output
from openjiuwen.core.runtime.base import ComponentExecutable
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.common.exception.exception import JiuWenBaseException
from openjiuwen.core.common.exception.status_code import StatusCode


def _ensure_update_global_state(runtime: Runtime):
    if hasattr(runtime, "update_global_state"):
        return

    def _update_global_state(updates: dict):
        state = runtime.state() if hasattr(runtime, "state") else None
        if state is None:
            raise JiuWenBaseException(StatusCode.RUNTIME_COMPONENT_ABILITY_NOT_IMPLEMENTED.code,
                                      "Runtime has no state()")

        if hasattr(state, "update_global_state"):
            try:
                return state.update_global_state(updates)
            except TypeError:
                pass
        if hasattr(state, "update_global"):
            try:
                return state.update_global(updates)
            except TypeError:
                for key, value in updates.items():
                    state.update_global(key, value)
                return None
        if hasattr(state, "set_global"):
            try:
                return state.set_global(updates)
            except TypeError:
                for key, value in updates.items():
                    state.set_global(key, value)
                return None

        for key, value in updates.items():
            if hasattr(state, "set"):
                try:
                    state.set(key, value)
                    continue
                except Exception:
                    pass
            raise JiuWenBaseException(StatusCode.RUNTIME_COMPONENT_ABILITY_NOT_IMPLEMENTED.code,
                                      "State does not support global updates")

    setattr(runtime, "update_global_state", _update_global_state)


class BaseNode(ComponentExecutable, WorkflowComponent):
    def __init__(self):
        super().__init__()

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        _ensure_update_global_state(runtime)
        if hasattr(self, "name"):
            try:
                runtime.update_global_state({"current_agent": getattr(self, "name")})
            except Exception:
                pass
        return await self._do_invoke(inputs, runtime, context)

    def _pre_handle(self, inputs: Input, runtime: Runtime, context: Context):
        raise JiuWenBaseException(StatusCode.RUNTIME_COMPONENT_ABILITY_NOT_IMPLEMENTED.code,
                                  "Node _pre_handle method not implemented.")

    def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        raise JiuWenBaseException(StatusCode.RUNTIME_COMPONENT_ABILITY_NOT_IMPLEMENTED.code,
                                  "Node _do_invoke method not implemented.")

    def _post_handle(self, inputs: Input, runtime: Runtime, context: Context):
        raise JiuWenBaseException(StatusCode.RUNTIME_COMPONENT_ABILITY_NOT_IMPLEMENTED.code,
                                  "Node _post_handle method not implemented.")


def init_router(current_node, next_nodes):
    router = BranchRouter()
    if isinstance(next_nodes, str):
        condition = f"${{{current_node}.next_node}} == {next_nodes!r}"
        router.add_branch(condition, next_nodes)
    elif isinstance(next_nodes, list):
        for next_node in next_nodes:
            condition = f"${{{current_node}.next_node}} == {next_node!r}"
            router.add_branch(condition, next_node)
    else:
        raise JiuWenBaseException(
            StatusCode.WORKFLOW_EXECUTE_INNER_ERROR.code,
            StatusCode.WORKFLOW_EXECUTE_INNER_ERROR.errmsg.format(next_nodes=next_nodes)
        )
    return router
