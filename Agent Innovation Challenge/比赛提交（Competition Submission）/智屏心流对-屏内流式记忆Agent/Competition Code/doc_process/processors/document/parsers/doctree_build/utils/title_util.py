# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module providing functions for title process."""
import re

RE_FIRST_TITLE = re.compile("(?<!\001)\001([^\001]+)\001(?!\001)")
RE_SECOND_TITLE = re.compile("(?<!\001)\001\001([^\001]+)\001\001(?!\001)")
RE_THIRD_TITLE = re.compile("(?<!\001)\001\001\001([^\001]+)\001\001\001(?!\001)")


def find_title(para):
    """
    Match first level title
    """
    title = ""
    if RE_FIRST_TITLE.search(para) is not None:
        # New Separator
        title = RE_FIRST_TITLE.search(para).group().replace("\001", "").strip()
    return title


def find_sub_title(para):
    """
    Match second level title
    """
    sub_title = ""
    if RE_SECOND_TITLE.search(para) is not None:
        # New Separator
        sub_titles = RE_SECOND_TITLE.findall(para)
        sub_title = sub_titles[0] if len(sub_titles) == 1 else ""
    return sub_title


def find_third_title(para):
    """
    Match third level title
    """
    third_title = ""
    if RE_THIRD_TITLE.search(para) is not None:
        # New Separator
        third_titles = RE_THIRD_TITLE.findall(para)
        third_title = third_titles[0] if len(third_titles) == 1 else ""
    return third_title
