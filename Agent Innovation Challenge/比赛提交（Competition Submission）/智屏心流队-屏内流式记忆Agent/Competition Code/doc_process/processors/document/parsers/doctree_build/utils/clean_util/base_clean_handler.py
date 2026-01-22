# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module providing a class to clean texts."""
import os
import re

from doc_process.processors.document.parsers.doctree_build.utils.clean_util.clean_re_rules import CLEAN_RE_RULES
from doc_process.processors.document.parsers.doctree_build.utils.path_util import get_white_list_info

WHITE_JSON_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "white_list.json"
)
white_list = get_white_list_info(WHITE_JSON_PATH)


class BaseCleanHandler:
    """ class for text clean """
    @staticmethod
    def clean_txt_all(text: str, file_type="ALL"):
        """ clean text by rules"""
        lines = text.split("\n")
        result_lines = []
        for line in lines:
            line = BaseCleanHandler.clean_garbled_characters(line)
            line = BaseCleanHandler.clean_email(line)
            line = BaseCleanHandler.clean_job_number(line)
            line = BaseCleanHandler.clean_multi_blank_character(line)
            line = BaseCleanHandler.clean_end(line)
            line = BaseCleanHandler.clean_multi_br(line)
            line = BaseCleanHandler.clean_single_btn(line)
            if file_type in ["pdf", "ALL"]:
                line = BaseCleanHandler.clean_abnormal_punctuation(line)
                line = BaseCleanHandler.clean_italicized_text(line)
            if line.strip() != "":
                result_lines.append(line)
        newline = "\n".join(result_lines)
        newline = BaseCleanHandler.clean_fig(newline)
        newline = BaseCleanHandler.clean_phone_number(newline)
        newline = BaseCleanHandler.clean_references(newline)
        newline = BaseCleanHandler.clean_copyright_information(newline)
        newline = BaseCleanHandler.clean_qq_number(newline)
        newline = BaseCleanHandler.clean_extra_punctuation(newline)
        newline = BaseCleanHandler.clean_multi_space(newline)
        # 删除多空行
        result_text = "\n".join([line for line in newline.splitlines() if line.strip()])
        return result_text

    @staticmethod
    def replace_char(key: str, replace_value: str, line: str, white_type=None) -> str:
        """ 替换字符 """
        white_info = white_list.get(white_type, [])

        re_lists = CLEAN_RE_RULES.get(key)
        for re_item in re_lists:
            if white_type == "w3姓名工号":
                line = BaseCleanHandler.replace_w3_person_msg(line, re_item, replace_value, white_info)
            else:
                line = BaseCleanHandler.replace_other_msg(line, re_item, replace_value, white_info)
        return line

    @staticmethod
    def replace_other_msg(line, re_item, replace_value, white_info):
        """ replace other msg """
        matches = [
            i[0] if isinstance(i, tuple) else i
            for i in re.findall(re_item, line)
        ]
        for match in matches:
            if match not in white_info:
                line = re.sub(re_item, replace_value, line)
        return line

    @staticmethod
    def replace_w3_person_msg(line, re_item, replace_value, white_info):
        """ replace w3 person msg """
        matches = [
            i[0] if isinstance(i, tuple) else i
            for i in re.findall(re_item, line)
        ]
        for match in matches:
            tag = False
            for white_member in white_info:
                if white_member in match:
                    tag = True
                    break
            if not tag:
                line = re.sub(re_item, replace_value, line)
        return line

    @staticmethod
    def replace_line_to_none(key: str, line: str) -> str:
        """ replace line with emtpy string """
        re_lists = CLEAN_RE_RULES.get(key)
        for re_item in re_lists:
            if re.search(re_item, line):
                return ""
        return line

    @staticmethod
    def clean_multi_br(line: str):
        """ 删除多余回车 """
        return BaseCleanHandler.replace_char("multi_br", "<br>", line)

    @staticmethod
    def clean_multi_space(line: str):
        """ 多余空格 """
        return BaseCleanHandler.replace_char("multi_space", " ", line)

    @staticmethod
    def clean_multi_blank_character(line: str):
        """ 删除空白字符 """
        return BaseCleanHandler.replace_char("multi_blank_character", " ", line)

    @staticmethod
    def clean_abnormal_punctuation(line: str):
        """ 删除疑似异常标点 """
        re_lists = CLEAN_RE_RULES.get("abnormal_punctuation")
        for re_item in re_lists:
            if re.search(re_item, line):
                if "袁" in re_item:
                    line = re.sub(r"袁", "。", line)
                elif "鄄" in re_item:
                    line = re.sub(r"鄄", "-", line)
        return line

    @staticmethod
    def clean_extra_punctuation(line: str):
        """ 删除多余标点符号 """
        white_info = white_list.get("多余标点符号", [])

        line = re.sub(r"。{2,}", "。", line)
        line = re.sub(r"!{2,}", "!", line)
        line = re.sub(r"！{2,}", "！", line)
        line = re.sub(r"，{2,}", "，", line)
        line = re.sub(r",{2,}", ",", line)
        line = re.sub(r"[?？]{2,}", "？", line)
        line = re.sub(r"(?<=\n)[,，。!！:：;；?？]+", "", line)

        matches = re.findall(r"[,，。!！:：;；?？]{2,}", line)
        for match in matches:
            if match not in white_info:
                punctuation = match[-1]
                line = line.replace(match, punctuation)
        return line

    @staticmethod
    def clean_bold_italic_return(line: str):
        """
        加粗文本（带**）;斜体文本（带*）
        """
        return line

    @staticmethod
    def clean_cell_br(line: str):
        """
        单元格内换行（<br>）  单元格内换行（\n\t）
        """
        return line

    @staticmethod
    def clean_revision_history(line: str):
        """
        删除修订记录
        """
        return BaseCleanHandler.replace_line_to_none("revision_history", line)

    @staticmethod
    def clean_italicized_text(line: str):
        """
        删除叠字文本
        """
        re_lists = CLEAN_RE_RULES.get("italicized_text")
        for re_item in re_lists:
            paragraphlist = re.findall(re_item, line)
            white_info = white_list.get("叠字文本")
            for res in paragraphlist:
                res_list = res[0]
                sub_list = "".join(res[i + 2] for i in range(0, len(res) - 2, 2))
                if res_list not in white_info:
                    line = line.replace(res_list, sub_list)
        return line

    @staticmethod
    def clean_garbled_characters(line: str):
        """
        删除疑似乱码
        """
        line = line.replace("犮现", "发现")
        line = line.replace("犮展", "发展")
        return BaseCleanHandler.replace_char(
            "garbled_characters", "", line, white_type="疑似乱码"
        )

    @staticmethod
    def clean_fig(line: str):
        """
        删除“如图”
        """
        re_lists = CLEAN_RE_RULES.get("fig")
        for re_item in re_lists:
            line = re.sub(re_item, "", line)
        return line

    @staticmethod
    def clean_references(line: str):
        """
        删除参考文献
        """
        return BaseCleanHandler.replace_char("references", "", line)

    @staticmethod
    def clean_email(line: str):
        """
        删除邮箱
        """
        return BaseCleanHandler.replace_char("email", " ", line)

    @staticmethod
    def clean_phone_number(line: str):
        """
        处理手机号
        """
        line = BaseCleanHandler.replace_char(
            "phone_number", " ", line, white_type="手机号"
        )
        regex_list = [
            r"[ :：(（“\n]*?(?:\+?\d+)?-?1[3-9]\d{9}[ )）”]?",
            r"[ :：(（“\n]*?\d{3,4}-?\d{8}[ )）”]?",
            r"[ :：(（“\n]*?106\d{5,10}(?!\d)[ )）”]?",
        ]
        phone_keyword = [
            "号码",
            "短信",
            "电话",
            "拨打",
            "热线",
            "咨询",
            "中国移动",
            "来电",
            "Mobile",
            "改号通知音",
            "联系人",
            "手机",
            "诈骗",
            "信息",
            "发送",
            "拨通",
            "华东分院",
            "消息",
            "助理",
            "领导",
            "接通",
            "彩信",
            "话费",
            "phone",
            "sms",
        ]

        for regex in regex_list:
            matches = re.findall(regex, line, re.S)
            for match in matches:
                line = BaseCleanHandler.replace_phone_number(line, match, phone_keyword)
        return line

    @staticmethod
    def replace_phone_number(line, match, phone_keyword):
        """ replace phone number """
        middle_string = line.split(match)[0]
        before_strings = middle_string[-20:]
        middle_string = line.split(match)[-1]
        after_string = middle_string[:20]
        for word in phone_keyword:
            if word in before_strings or word in after_string:
                line = line.replace(str(match), " ")
                break
        return line

    @staticmethod
    def clean_copyright_information(line: str):
        """
        删除版权信息
        """
        return BaseCleanHandler.replace_char("copyright_information", "", line)

    @staticmethod
    def clean_job_number(line: str):
        """
        删除w3姓名工号
        """
        return BaseCleanHandler.replace_char(
            "job_number", "", line, white_type="w3姓名工号"
        )

    @staticmethod
    def clean_end(line: str):
        """
        删除多余空行
        """
        return BaseCleanHandler.replace_char("end_str", "", line)

    @staticmethod
    def clean_qq_number(line: str):
        """
        删除QQ号
        """
        return BaseCleanHandler.replace_char("qq_number", " ", line)

    @staticmethod
    def clean_single_btn(line: str):
        """
        删除单个按钮文本
        """
        return " ".join([BaseCleanHandler.replace_char("single_btn", "", s.strip()) for s in line.split(" ")])
