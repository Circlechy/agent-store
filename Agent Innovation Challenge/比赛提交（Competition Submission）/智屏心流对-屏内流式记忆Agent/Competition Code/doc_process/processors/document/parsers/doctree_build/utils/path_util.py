# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module providing path util functions."""
import json
import os
import stat


def get_white_list_info(path):
    """ get white list information """
    modes = stat.S_IWUSR | stat.S_IRUSR
    with os.fdopen(
        os.open(path, os.O_RDWR | os.O_CREAT, modes), "r+", encoding="utf-8"
    ) as f:
        json_obj = json.load(f)
    return json_obj
