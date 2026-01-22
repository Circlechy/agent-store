# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module providing others utils."""
import json

from unidecode import unidecode

ZH_PUNCS = set("！？｡＂＃＄％＆＇（）＊＋，－／：；＜＝＞［＼］＾＿｀｛｜｝～｟｠｢｣､、〃》「」『』【】〔〕〖〗〘〙〚〛〜〝〞–—‘’‛“”„‟.−")
ZH_SPECIAL_PUNC_MAPPING = {"ꎬ": "，", "ꎮ": "。", "ꎻ": "；"}


def check_zh(s):
    """ check if text is chinese text """
    for ch in s:
        if u"\u4e00" <= ch <= u"\u9fff":
            return True
    return False


def is_zh_punc(char):
    """ check if character is chinese punctuation """
    if u"\u3000" <= char <= u"\u303f":
        return True
    if char in ZH_PUNCS:
        return True
    return False


def is_ascii(char):
    """ check if character is english or number"""
    if u"\u0020" <= char <= u"\u007f":  # basic latin
        return True
    return False


def remove_illegal_chars(text):
    """ remove iilegal chars """
    new_content = ""
    for c in text:
        if is_ascii(c) or check_zh(c) or is_zh_punc(c):
            new_content += c
        elif c in ZH_SPECIAL_PUNC_MAPPING:
            new_content += ZH_SPECIAL_PUNC_MAPPING.get(c)
        else:
            c_converted = unidecode(c)
            if len(c_converted) == 1 and is_ascii(c_converted):     # special latin char to latin (only digit and Aa-Zz)
                new_content += c_converted
            else:
                new_content += c
    return new_content


class ConfigItem(dict):
    """ config item """

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self

    def __str__(self):
        return json.dumps(self.to_dict(self))

    @staticmethod
    def from_dict(input_):
        """ construct config from dict """
        if isinstance(input_, dict):
            config_dict = ConfigItem()
            for k, v in input_.items():
                setattr(config_dict, k, ConfigItem.from_dict(v))
            return config_dict
        if isinstance(input_, list):
            return [ConfigItem.from_dict(v) for v in input_]
        return input_

    @staticmethod
    def to_dict(input_):
        """ convert config to dict """
        if isinstance(input_, ConfigItem):
            return {k: ConfigItem.to_dict(v) for k, v in input_.__dict__.items()}
        if isinstance(input_, list):
            return [ConfigItem.to_dict(v) for v in input_]
        return input_

    @classmethod
    def merge_dict_cfg(cls, cfg1, cfg2):
        """ update config """
        for k in list(cfg1.keys()) + list(cfg2.keys()):
            if k not in cfg2:
                continue
            v1, v2 = cfg1.get(k), cfg2.get(k)
            if isinstance(v1, dict) and isinstance(v2, dict):
                cfg1[k] = cls.merge_dict_cfg(v1, v2)
            else:
                cfg1[k] = v2
        return cfg1
