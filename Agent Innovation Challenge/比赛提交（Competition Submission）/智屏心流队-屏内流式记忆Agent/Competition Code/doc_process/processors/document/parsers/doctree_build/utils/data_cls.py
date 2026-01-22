# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
"""Module base schema."""
import itertools
from typing import List
import json

from doc_process.context.doc_constants import TREE_KEY, FILE_NAME_KEY
from doc_process.utils.error_code import ProcessorException, ErrorCode


class LabelDict:
    """ Node labels """
    TITLE = ["Title", "Title_1", "Title_2", "Title_3"]
    CONTENT = "Content"
    TABLE = "Table"


class TableSep:
    """ Table seps """
    LINE, CELL = "#LineSEP#", "#CellSEP#"
    START = "#TableSTART#"
    END = "#TableEND#"
    NAME_SEP = "#TableNameSEP#"

    @classmethod
    def get_all_tablesep(cls):
        """ get all table seps """
        return [cls.LINE, cls.CELL, cls.START, cls.END, cls.NAME_SEP]


class Node:
    """ Node of parse file """

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", -1)
        self.page_id = kwargs.get("page_id", -1)

        self.label = kwargs.get("label", None)
        self.layout_model_label = None
        self.title_level = 1

        self.text = kwargs.get("text", "")
        self.size = float(kwargs.get("size")) if "size" in kwargs else 0.0
        self.loc = list(kwargs.get("loc", []))
        self.font_name = str(kwargs.get("font_name")) if "font_name" in kwargs else ""

        self.parent = None
        self.children = []

    def __str__(self):
        return "({}) {}".format(self.label, self.text)

    def __eq__(self, other):
        if set(self.__dict__.keys()) != set(other.__dict__.keys()):
            return False
        for attr in self.__dict__:
            if attr == "parent":
                continue
            if not getattr(self, attr) == getattr(other, attr):
                return False
        return True

    def __hash__(self):
        return hash(self.to_dict()[1])

    @classmethod
    def from_dict(cls, d):
        """ restore node from dict """
        if isinstance(d, str):
            d = json.loads(d)
        node = cls(**d)
        if d.get("children"):
            node.children = [cls.from_dict(child_d) for child_d in d["children"]]
            for child_node in node.children:
                child_node.parent = node
        return node

    def to_dict(self):
        """ node to dict """
        d = {}
        for attr, value in self.__dict__.items():
            if attr == "parent":
                continue
            if attr == "children":
                d[attr] = [child.to_dict()[0] for child in value]
            else:
                d[attr] = value
        return d, json.dumps(d, ensure_ascii=False)

    def flat_with_children(self, clear_structure=False):
        """ restore node list from structured node """
        child_nodes = list(itertools.chain.from_iterable([child.flat_with_children() for child in self.children]))
        if clear_structure:
            self.parent = None
            self.children = []
        return [self] + child_nodes

    def get_brief_text(self, brief_len=30):
        """ get brief text for node """
        if len(self.text) <= brief_len * 2:
            return self.text
        brief_text = "{} ...({})... {}".format(self.text[:brief_len],
                                               len(self.text) - 2 * brief_len,
                                               self.text[-brief_len:])
        brief_text = brief_text.replace("\n", "\\n")
        return brief_text

    def visualize_with_children(self, indent=0, brief_len=30):
        """ visualize node with children """
        lines = []
        text = self.get_brief_text(brief_len)
        lines.append("{} | ({}) {}".format("\t" * indent, self.label, text.replace("\n", "\\n")))
        for child in self.children:
            child_lines = child.visualize_with_children(indent=indent + 1, brief_len=brief_len)
            lines += child_lines
        return lines


class DocTree:
    """ DocTree for parsed file """

    def __init__(self, root_node: Node, nodes: List[Node], file_name=""):
        self.root_node = root_node
        self.nodes = nodes
        self.file_name = file_name

    def __str__(self):
        return "DocTree with {} nodes:\n{}".format(len(self.nodes), self.visualize())

    def __eq__(self, other):
        if set(self.__dict__.keys()) != set(other.__dict__.keys()):
            return False
        for attr in self.__dict__:
            if not getattr(self, attr) == getattr(other, attr):
                return False
        return True

    @classmethod
    def from_dict(cls, d):
        """ restore doctree from dict """
        if isinstance(d, str):
            d = json.loads(d)
        for key in [TREE_KEY, FILE_NAME_KEY]:
            if key not in d:
                raise ProcessorException(ErrorCode.VALUE_ERROR, "Key '{}' missed.".format(key))
        root_node = Node.from_dict(d.get(TREE_KEY))
        return cls(root_node=root_node, nodes=root_node.flat_with_children(), file_name=d.get(FILE_NAME_KEY))

    @classmethod
    def from_node_list(cls, nodes: List[Node], file_title=""):
        """ construct doctree from node list """
        nodes = [node for node in nodes if node.label in LabelDict.TITLE or node.text != ""]
        nodes_text = "".join([node.text for node in nodes])
        if len(nodes_text) == 0:
            raise ProcessorException(ErrorCode.EMPTY_FILE, "No file content parsed.")

        # init root_node
        root_node = Node(text=file_title, label=LabelDict.TITLE[0])  # 文档标题设置为0级
        for node in nodes:
            if node.label == LabelDict.TITLE[0]:
                root_node = node
                nodes.remove(node)
                break

        if not nodes:
            return cls(root_node=root_node, nodes=[root_node], file_name=file_title)

        # merge near content nodes
        merged_nodes = [nodes[0]]
        for node in nodes[1:]:
            if node.label == merged_nodes[-1].label and node.label == LabelDict.CONTENT:
                prev_node = merged_nodes.pop()
                merged_nodes.append(Node(text=prev_node.text + "\n" + node.text, label=node.label))
            else:
                merged_nodes.append(node)
        nodes = merged_nodes

        # update node id
        for i, node in enumerate(nodes):
            node.id = i

        # link node to nearest title node
        title_stack = [root_node]
        for node in nodes:
            # normal node (content, table...)
            if node.label not in LabelDict.TITLE:
                title_stack[-1].children.append(node)
                node.parent = title_stack[-1]
                continue
            # title node
            while LabelDict.TITLE.index(node.label) <= LabelDict.TITLE.index(title_stack[-1].label):
                title_stack.pop()
            title_stack[-1].children.append(node)
            node.parent = title_stack[-1]
            title_stack.append(node)
        return cls(root_node=root_node, nodes=[root_node] + nodes, file_name=file_title)

    def visualize(self, brief_len=30):
        """ visualize doctree """
        return "\n".join(self.root_node.visualize_with_children(brief_len=brief_len))

    def to_dict(self):
        """ doctree to dict """
        tree_dict, _ = self.root_node.to_dict()
        d = {FILE_NAME_KEY: self.file_name, TREE_KEY: tree_dict}
        return d, json.dumps(d, ensure_ascii=False)
