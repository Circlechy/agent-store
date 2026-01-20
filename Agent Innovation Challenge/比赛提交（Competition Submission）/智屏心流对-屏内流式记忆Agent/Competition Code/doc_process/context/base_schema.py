#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


import json
from abc import abstractmethod
from enum import Enum, auto
from io import BytesIO
from typing import Any, Dict, Optional, Union

from doc_process.utils import logging
from doc_process.utils.check_utils import CheckUtils
from doc_process.context.doc_constants import DEFAULT_KNOWLEDGE_BASE_NAME, ProcessorName
from doc_process.utils.error_code import ProcessorException
from doc_process.utils.pydantic import BaseModel, Field

ImageType = Union[str, BytesIO]
logger = logging.get_logger()


class StreamType(int, Enum):
    """Stream type used in `StreamType` class.

    Attributes:
        REAL: Stand for real increase data.
        STATIC: Stand for static index data.
    """
    REAL = auto()
    STATIC = auto()


class BaseData(BaseModel):
    """Base class for data objects"""


class Context(BaseModel):
    """Base class for context"""
    verbose: bool = Field(
        default=False,
        description="verbose"
    )
    knowledge_base_name: str = Field(
        default=DEFAULT_KNOWLEDGE_BASE_NAME,
        description="knowledge_base_name"
    )
    session_id: str = Field(
        default="",
        description="session_id"
    )
    stream_type: StreamType = Field(
        default=StreamType.STATIC,
        description="stream_type"
    )
    input_kwargs: dict = Field(
        default=dict(),
        description="input kwargs from Input parameters of the service interface"
    )
    component_info: Dict[ProcessorName, Dict[str, ProcessorException]] = Field(
        default=dict(),
        description="process info for each component"
    )

    pipeline_response: dict = Field(
        default={"code": 0, "msg": ""},
        description="response of after finishing pipeline"
    )

    class Config:
        """Config object."""
        arbitrary_types_allowed = True

    def get_knowledge_base_name(self) -> str:
        """get knowledge_base_name"""
        return self.knowledge_base_name

    def set_knowledge_base_name(self, knowledge_base_name: str) -> None:
        """set knowledge_base_name"""
        self.knowledge_base_name = knowledge_base_name

    def get_session_id(self) -> str:
        """get session_id"""
        return self.session_id

    def set_session_id(self, session_id: str) -> None:
        """set session_id"""
        self.session_id = session_id

    def get_stream_type(self) -> StreamType:
        """get stream_type"""
        return self.stream_type

    def set_stream_type(self, stream_type: StreamType) -> None:
        """get stream_type"""
        self.stream_type = stream_type

    def get_verbose(self) -> bool:
        """Get verbose"""
        return self.verbose

    def set_verbose(self, verbose: bool) -> None:
        """Set verbose"""
        self.verbose = verbose

    def get_input_kwargs(self) -> dict:
        """Get input_kwargs"""
        return self.input_kwargs

    def get_input_kwarg_with_key(self, key):
        """Get input_kwarg"""
        return self.input_kwargs.get(key, None)

    def update_input_kwargs(self, kwargs_name: str, value: Any) -> None:
        """update input_kwargs value"""
        self.input_kwargs[kwargs_name] = value

    def update_input_kwargs_with_dict(self, input_dict: dict) -> None:
        """update input_kwargs with dict"""
        self.input_kwargs.update(input_dict)

    def get_component_info(self) -> dict:
        """Get response"""
        return self.component_info

    def update_component_info(self, component_name: ProcessorName, value: Dict[str, ProcessorException]) -> None:
        """update response value"""
        CheckUtils.check_type(component_name, ProcessorName, "component_name")
        CheckUtils.check_dict(value, str, ProcessorException)
        self.component_info[component_name] = value

    def add_info_to_component(self, component_name: ProcessorName, key: str, value: ProcessorException) -> None:
        """add response to specific component"""
        CheckUtils.check_type(component_name, ProcessorName, "component_name")
        CheckUtils.check_type(key, str)
        CheckUtils.check_type(value, ProcessorException)
        if component_name in self.component_info:
            self.component_info[component_name][key] = value
        else:
            self.component_info[component_name] = dict()
            self.component_info[component_name][key] = value

    def get_cost_time(self) -> dict:
        """Get cost_time"""
        return self.pipeline_response.get("cost_time", dict())

    def update_cost_time(self, component_name: str, value: str) -> None:
        """update cost_time value"""
        cost_time = self.get_cost_time()
        cost_time[component_name] = value
        self.pipeline_response["cost_time"] = cost_time

    def set_code(self, code: int) -> None:
        """Set response code"""
        self.pipeline_response["code"] = code

    def set_msg(self, msg: str) -> None:
        """Set response msg"""
        self.pipeline_response["msg"] = msg

    def set_success_count(self, success_count: int) -> None:
        """Set response total success count"""
        self.pipeline_response["success_count"] = success_count if success_count >= 0 else 0

    def get_pipeline_response(self) -> dict:
        """Get response"""
        return self.pipeline_response

    def to_dict(self) -> dict:
        """context to dict"""
        return {"verbose": self.verbose,
                "component_info": self.component_info,
                "pipeline_response": self.pipeline_response}


class BaseComponent(BaseModel):
    """Base component object to capture class names"""

    class Config:
        """base component config object."""

        @staticmethod
        def schema_extra(schema: Dict[str, Any], model: "BaseComponent") -> None:
            """Add class name to schema."""
            schema["properties"]["class_name"] = {
                "title": "Class Name",
                "type": "string",
                "default": model.class_name(),
            }

    def __getstate__(self) -> Dict[str, Any]:
        state = super().__getstate__()

        # tiktoken is not pickleable
        dt = "__dict__"
        state[dt].pop("tokenizer", None)

        # remove local functions
        keys_to_remove = []
        for key, val in state[dt].items():
            if key.endswith("_fn"):
                keys_to_remove.append(key)
            if "<lambda>" in str(val):
                keys_to_remove.append(key)
        for key in keys_to_remove:
            state[dt].pop(key, None)

        # remove private attributes -- kind of dangerous
        pav = "__private_attribute_values__"
        state[pav] = {}

        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        # Use the __dict__ and __init__ method to set state
        # so that all variable initialize
        try:
            self.__init__(**state["__dict__"])  # type: ignore
        except Exception:
            # Fall back to the default __setstate__ method
            super().__setstate__(state)

    @classmethod
    def class_name(cls) -> str:
        """
        Get the class name, used as a unique ID in serialization.
        """
        return "base_component"

    @classmethod
    def from_dict(cls, data: Dict[str, Any], **kwargs: Any) -> BaseModel:  # type: ignore
        """From dict to BaseModel"""
        if isinstance(kwargs, dict):
            data.update(kwargs)

        data.pop("class_name", None)
        return cls(**data)

    @classmethod
    def from_json(cls, data_str: str, **kwargs: Any) -> BaseModel:  # type: ignore
        """From json to BaseModel"""
        data = json.loads(data_str)
        return cls.from_dict(data, **kwargs)

    def json(self, **kwargs: Any) -> str:
        """To json string"""
        return self.to_json(**kwargs)

    def dict(self, **kwargs: Any) -> Dict[str, Any]:
        """To dict"""
        data = super().dict(**kwargs)
        data["class_name"] = self.class_name()
        return data

    def to_dict(self, **kwargs: Any) -> Dict[str, Any]:
        """To dict"""
        data = self.dict(**kwargs)
        data["class_name"] = self.class_name()
        return data

    def to_json(self, **kwargs: Any) -> str:
        """To json"""
        data = self.to_dict(**kwargs)
        return json.dumps(data, ensure_ascii=False)


class ProcessComponent(BaseComponent):
    """Base class for process components"""

    class Config:
        """Config object."""
        arbitrary_types_allowed = True

    @abstractmethod
    def __call__(self, context: Optional[Context], **kwargs: Any) -> None:
        """process components."""

    @abstractmethod
    def _parse_input(self, context: Optional[Context], **kwargs: Any) -> None:
        """parse input"""
