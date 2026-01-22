# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
""" Module providing TextSegmentor for SegmentorBasedSplitter """
import re

from doc_process.utils.error_code import ProcessorException, ErrorCode


def check_zh(s):
    """ check if text is chinese text """
    for ch in s:
        if u"\u4e00" <= ch <= u"\u9fff":
            return True
    return False


class TextSegmentor:
    """
    对纯文本进行切分
    """

    def __init__(self, config):
        self.target_length = config.get("target_length")
        overlap_ratio = config.get("overlap_ratio")
        if overlap_ratio < 0 or overlap_ratio >= 1:
            raise ProcessorException(ErrorCode.VALUE_ERROR,
                                     "Wrong overlap_ratio {}. (0 <= overlap_ratio < 1".format(overlap_ratio))
        self.overlap_len = int(config.get("overlap_ratio") * self.target_length)

    def segment(self, text):
        """
        将文本切分成小片段后，再根据设定的最大长度做拼接
        """
        frags = self._get_frags(text)
        segs, seg_frags = [""], [[]]
        for frag in frags:
            if len(segs[-1] + frag) > self.target_length:
                overlap_text = self._get_overlap_text(seg_frags[-1])
                if overlap_text == segs[-1]:  # overlap和segs[-1]一致，即segs[-1]会被当前文本包含，因此须去掉segs[-1]避免重复
                    segs.pop()
                else:
                    seg_frags.append([])
                segs.append(overlap_text + frag)
                seg_frags[-1].append(frag)
            else:
                segs[-1] += frag
                seg_frags[-1].append(frag)
        segs = [x.strip() for x in segs if x.strip()]
        return segs

    def _plain_text_to_frags(self, text):
        """
        对纯文本做切分
        """
        raise NotImplementedError

    def _text_list_to_frags(self, text_list):
        """
        对text_list中的text分别做切分
        :param text_list: List[(text, need_segment))]，(文本，文本是否需要被切分)
        """
        raise NotImplementedError

    def _get_frags(self, text):
        """
        输入纯文本则直接切分；输入list，则根据是否需要切分分别处理，适用于部分文本块不作切分的情景（例如表格、标题）
        """
        if isinstance(text, list):
            frags = self._text_list_to_frags(text)
        else:
            frags = self._plain_text_to_frags(text)
        return frags

    def _get_overlap_text(self, frags):
        """
        根据组成上一segment的frags和指定的overlap长度，获取片段之间重叠的frag，并拼接成文本
        """
        overlap_text = ""
        for frag in frags[::-1]:
            if len(overlap_text) >= self.overlap_len:
                return overlap_text
            overlap_text = frag + overlap_text
        return overlap_text


class FixLenSegmentor(TextSegmentor):
    """
    根据固定长度对文本做切分
    """

    def _plain_text_to_frags(self, text):
        """
        对纯文本做切分
        """
        return list(text) + ["\n"]

    def _text_list_to_frags(self, text_list):
        """
        对text_list中的text分别做切分
        :param text_list: List[(text, need_segment))]，(文本，文本是否需要被切分)
        """
        frags = []
        for text, need_segment in text_list:
            if not need_segment:
                frags.append(text)
            else:
                frags.extend(list(text))
            frags.append("\n")
        return frags


class PuncSegmentor(TextSegmentor):
    """
    根据标点对文本做切分
    """

    def __init__(self, config):
        """
        :param segment_puncs: 切分符
        """
        super(PuncSegmentor, self).__init__(config)
        self.en_segment_puncs = config.get("en_segment_puncs")
        self.zh_segment_puncs = config.get("zh_segment_puncs")

    def _plain_text_to_frags(self, text):
        """
        对纯文本做切分
        """
        segment_puncs = self.zh_segment_puncs if check_zh(text) else self.en_segment_puncs
        frags_and_puncs = re.split("({})".format(segment_puncs), text)
        frags_and_puncs.append("")  # padding，便于后续文本与序号连接
        # 复原符号
        frags = ["".join(pair) for pair in zip(frags_and_puncs[0::2], frags_and_puncs[1::2]) if pair[0]]
        return frags

    def _text_list_to_frags(self, text_list):
        """
        对text_list中的text分别做切分
        :param text_list: List[(text, need_segment))]，(文本，文本是否需要被切分)
        """
        frags = []
        for text, need_segment in text_list:
            text = text + "\n"
            if not need_segment:  # 例如table、title不需要被切分
                frags.append(text)
            else:
                frags.extend(self._plain_text_to_frags(text))
        return frags


SEGMENTOR_CLS = {
    "fixlen": FixLenSegmentor,
    "punc": PuncSegmentor
}
