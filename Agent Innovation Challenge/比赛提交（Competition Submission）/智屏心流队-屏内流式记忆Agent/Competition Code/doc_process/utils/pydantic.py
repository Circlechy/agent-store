#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


try:
    import pydantic.v1 as pydantic
    from pydantic.v1 import (
        BaseConfig,
        BaseModel,
        Field,
    )
    from pydantic.v1.error_wrappers import ValidationError
    from pydantic.v1.fields import FieldInfo
    from pydantic.v1.generics import GenericModel
except ImportError:
    import pydantic  # type: ignore
    from pydantic import (
        BaseConfig,
        BaseModel,
        Field,
    )
    from pydantic.error_wrappers import ValidationError
    from pydantic.fields import FieldInfo
    from pydantic.generics import GenericModel

__all__ = [
    "pydantic",
    "BaseConfig",
    "BaseModel",
    "Field",
    "FieldInfo",
    "ValidationError",
    "GenericModel",
]
