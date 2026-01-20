#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
from functools import wraps
from contextlib import ContextDecorator

from doc_process.context.base_schema import Context
from doc_process.context.multimodal_schema import MultimodalContext


class StreamManager(ContextDecorator):
    """流处理装饰器（自动管理流索引）"""

    def __init__(self, func):
        self.func = func
        wraps(func)(self)  # 保持元数据

    def __get__(self, instance, owner):
        """通过描述符协议绑定类实例"""

        def wrapper(context: Context, **kwargs):
            class_name = instance.__class__.__name__  # 动态获取类名

            last_index = context.get_multimodal().get_stream_index_with_key(class_name)
            stream = context.get_multimodal().get_multimodal_streams()[last_index + 1]

            # 执行原始方法
            self.func(instance, stream, **kwargs)

            # 更新索引
            context.get_multimodal().update_stream_index(class_name, last_index + 1)

        return wrapper
