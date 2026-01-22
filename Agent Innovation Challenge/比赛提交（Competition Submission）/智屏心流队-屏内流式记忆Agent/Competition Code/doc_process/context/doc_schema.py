#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.


import itertools
import uuid
from abc import abstractmethod
from enum import Enum, auto
from io import BytesIO
from typing import Any, Dict, List, Optional, Union

from doc_process.context.base_schema import Context, BaseData, StreamType
from doc_process.utils import logging
from doc_process.context.doc_constants import FILES_TOTAL_COUNT
from doc_process.utils.error_code import ProcessorException, ErrorCode
from doc_process.utils.pydantic import BaseModel, Field

ImageType = Union[str, BytesIO]
logger = logging.get_logger()


class ChunkType(str, Enum):
    """Document type used in `DocumentType` class.

    Attributes:
        DOCUMENT: Stand for whole file.
        CHUNK: Stand for chunk of file.
        SUMMARY: Stand for summary chunk of file.
    """
    TEXTCONTENT = auto()
    TABLECONTENT = auto()
    PICTURECONTENT = auto()
    SUMMARY = auto()


class TableHeader(str, Enum):
    """Table header used in `TABLECONTENT` class.

    Attributes:
        FIRSTROW: The first row of table is header.
        FIRSTCOLUMN: The first column of table is header.
        BOTH: Both first row and first column of table is header.

    """

    FIRSTROW = auto()
    FIRSTCOLUMN = auto()
    BOTH = auto()


class DocumentRelationship(str, Enum):
    """Chunk relationships used in `Document` class.

    Attributes:
        SOURCE: The chunk is the source document.
        PREVIOUS: The chunk is the previous chunk in the document.
        NEXT: The chunk is the next chunk in the document.
        PARENT: The chunk is the parent chunk in the document.
        CHILD: The chunk is a child chunk in the document.

    """

    SOURCE = auto()
    PREVIOUS = auto()
    NEXT = auto()
    PARENT = auto()
    CHILD = auto()


class RelatedChunkInfo(BaseModel):
    """Relate chunk info object."""
    chunk_id: str

    @classmethod
    def class_name(cls) -> str:
        """class name"""
        return "RelatedChunkInfo"


class BaseContent(BaseModel):
    """Base contetn Object.

    Generic abstract interface for document/chunk content

    """

    @classmethod
    def class_name(cls) -> str:
        """get class name"""
        return "BASECONTENT"

    @abstractmethod
    def to_string(self) -> str:
        """convert content to string"""
        ...


class TextContent(BaseContent):
    """Base contetn Object.

    Generic abstract interface for document/chunk content

    """
    content: str

    @classmethod
    def class_name(cls) -> str:
        """get class name"""
        return "TEXTCONTENT"

    def set_content(self, value: str) -> None:
        """Set the content of the node."""
        self.content = value

    def to_string(self) -> str:
        """convert content to string"""
        return self.content


class TableContent(BaseContent):
    """chunk with table"""
    title: Optional[str] = None
    placeholder: Optional[str] = None
    table: Optional[List[List[str]]] = Field(
        default=None,
        description="table content 2d list",
    )
    header: Optional[TableHeader] = None

    @classmethod
    def class_name(cls) -> str:
        return "TABLECONTENT"

    def to_string(self) -> str:
        table_cells = list(itertools.chain.from_iterable(self.table))
        if self.title:
            return " ".join([self.title] + table_cells)
        return " ".join(table_cells)


class ImageContent(BaseContent):
    """chunk with image"""

    # store reference instead of actual image
    # base64 encoded image str
    image: Optional[str] = None
    title: Optional[str] = None
    path: Optional[str] = None
    url: Optional[str] = None
    placeholder: Optional[str] = None
    embedding: Optional[List[float]] = Field(
        default=None,
        description="embedding of image",
    )
    content: Optional[List[str]] = Field(
        default=None,
        description="text of image by ocr or ...",
    )

    @classmethod
    def class_name(cls) -> str:
        """image content"""
        return "ImageContent"

    def to_string(self) -> str:
        """to string"""
        if self.title:
            return " ".join([self.title] + self.content)
        return " ".join(self.content)

    def resolve_image(self) -> ImageType:
        """Resolve an image such that PIL can read it."""
        if self.image is not None:
            import base64

            return BytesIO(base64.b64decode(self.image))
        if self.path is not None:
            return self.path
        if self.url is not None:
            # load image from URL
            import requests

            response = requests.get(self.url)
            return BytesIO(response.content)
        logger.error("No image found in chunk.")
        return ""


class Inverted(BaseModel):
    """Inverted for building index"""
    tokens: List[str] = []
    pos: List[int] = []


class Semantic(BaseModel):
    """section info for building index"""
    id: str = ""
    embeddings: List[float] = []


class IndexInfo(BaseModel):
    """section info for building index"""

    section: Optional[str] = Field(
        default=""
    )
    inverted: Optional[Inverted] = Field(
        default=Inverted(),
        description="for building inverted index of section",
    )
    semantics: Optional[List[Semantic]] = Field(
        default=[],
        description="embedding of section, maybe has multiple embeddings",
    )


class Chunk(BaseModel):
    """Chunk of document

    Generic abstract interface for chunk content

    """

    doc_node_id: str = Field(
        default="",
        description="ID of the document node.",
    )
    chunk_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID of the chunk.",
    )
    chapter: Optional[List[str]] = Field(
        default_factory=None,
        description="route from document root to leaf.",
    )
    content: BaseContent
    chunk_type: ChunkType
    chunk_metadata: dict = Field(
        default=dict()
    )

    index_infos: Optional[Dict[str, IndexInfo]] = Field(
        default_factory=dict
    )

    def get_chunk_id(self) -> str:
        """
        get chunk_id
        """
        return self.chunk_id

    def get_content(self) -> str:
        """
        get content string
        """
        return self.content.to_string()

    def get_title(self) -> str:
        """get title string"""
        return " ".join(self.chapter)

    def get_chapter_summary(self) -> str:
        """
        get chapter_summary
        """
        return self.chunk_metadata.get("CHAPTER_SUMMARY", "")

    def get_chunk_metadata(self) -> dict:
        """
        get chunk_metadata
        """
        return self.chunk_metadata

    def set_chapter_summary(self, value):
        """
        set chapter_summary
        """
        self.chunk_metadata["CHAPTER_SUMMARY"] = value


class DocNode(BaseModel):
    """Node of document tree

    Generic abstract interface for document content

    """

    chapter: Optional[List[str]] = Field(
        default_factory=None,
        description="route from document root to leaf.",
    )
    title_level: Optional[int] = Field(
        default_factory=None,
        description="the deepest title level of chapter"
    )
    content: List[BaseContent]
    parent: Optional[List] = Field(
        default_factory=None,
        description="parent node of current node"
    )
    children: Optional[List] = Field(
        default_factory=None,
        description="child node of parent node"
    )
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID of the node."
    )

    def flat_with_children(self):
        """flat with children"""
        return [self] + list(
            itertools.chain.from_iterable([child_node.flat_with_children() for child_node in self.children]))


class ChapterNode(BaseModel):
    """
    文档摘要树的节点对象
    """

    current_chapter: Optional[List[str]] = Field(
        default=[]
    )
    node_header: str = Field(
        default=""
    )
    parent_header: str = Field(
        default=""
    )
    children_chapter: List[str] = Field(
        default=[]
    )
    node_summary: str = Field(
        default=""
    )

    def __str__(self) -> str:
        return "{}".format(self.node_summary)


class SummaryTree(BaseModel):
    """
    文档摘要树对象
    """

    doc_title: str = Field(
        default=""
    )
    knowledge_base_name: str = Field(
        default=""
    )
    doc_root_node: DocNode = Field(
        description="root node of SummaryTree"
    )
    chapter_tree: List[ChapterNode] = Field(
        default=[]
    )

    def __str__(self) -> str:
        display = "Doc {} with {} chapter nodes:\n".format(self.doc_title, len(self.chapter_tree))
        root_chapter_node = self.get_root_chapter_node()
        display += str(root_chapter_node) if root_chapter_node is not None else ""
        return display

    @classmethod
    def from_chapter_node_list(cls, doc_root_node: DocNode, chapter_node_list: List[ChapterNode], doc_title: str = "",
                               knowledge_base_name: str = ""):
        """chapter node list"""
        return cls(doc_title=doc_title, knowledge_base_name=knowledge_base_name, doc_root_node=doc_root_node,
                   chapter_tree=chapter_node_list)

    @classmethod
    def build_chapter_nodes_from_doc_tree(cls, doc_root_node: DocNode, parent_header=None, deep_num=""):
        """Build chapter nodes from document tree"""
        node_header = " ".join(
            [deep_num, doc_root_node.chapter[-1].strip()]).strip() if doc_root_node.chapter is not None and len(
            doc_root_node.chapter) > 0 else ""

        children = doc_root_node.children if doc_root_node.children is not None else []
        children_chapter_list = []
        descendant_chapter_list = []
        for child_idx, child in enumerate(children):
            child_deep_num = ".".join([deep_num, str(child_idx + 1)]) if deep_num != "" else str(child_idx + 1)
            child_chapter_node, descendant_chapter_nodes = cls.build_chapter_nodes_from_doc_tree(
                child, node_header, child_deep_num)
            children_chapter_list.append(child_chapter_node)
            descendant_chapter_list.extend(descendant_chapter_nodes)

        parent_header = parent_header.strip() if parent_header is not None and parent_header.strip() != "" else ""
        node_summary = "\n".join([node_header] + [node.node_summary for node in children_chapter_list])
        chapter_node = ChapterNode(current_chapter=doc_root_node.chapter, node_header=node_header,
                                   parent_header=parent_header,
                                   children_chapter=[node.node_header for node in children_chapter_list],
                                   node_summary=node_summary)
        return chapter_node, [chapter_node] + descendant_chapter_list

    @classmethod
    def from_doc_root_node(cls, doc_root_node: DocNode, doc_title: str = "", knowledge_base_name: str = ""):
        """from document root node"""
        _, chapter_node_list = cls.build_chapter_nodes_from_doc_tree(doc_root_node)
        """From document root node"""
        return cls.from_chapter_node_list(doc_root_node, chapter_node_list, doc_title, knowledge_base_name)

    def get_chapter_node(self, chapter: List[str]) -> Union[ChapterNode, None]:
        """Get chapter node"""
        if chapter is None or len(chapter) == 0 or self.chapter_tree is None:
            return None

        for node in self.chapter_tree:
            if node.current_chapter == chapter:
                return node
        return None

    def get_root_chapter_node(self) -> Union[ChapterNode, None]:
        """Get root chapter node"""
        return self.chapter_tree[0] if self.chapter_tree is not None and len(self.chapter_tree) > 0 else None


class SummaryForest(BaseModel):
    """
    文档集摘要树对象
    """

    summary_set: Dict[str, SummaryTree] = Field(
        default_factory=dict,
        description="each items for one SummaryTree"
    )

    def __str__(self) -> str:
        display = "ALL {} Documents:\n".format(len(self.summary_set.keys()))
        for _, summary_value in self.summary_set.items():
            display += str(summary_value) + "\n"
        return display.strip("\n")

    def update(self, summary: SummaryTree):
        """update summary tree"""
        self.summary_set.setdefault(summary.doc_title, summary)

    def get(self, doc_title: str) -> SummaryTree:
        """Get summarg tree"""
        return self.summary_set.get(doc_title, None)


class Document(BaseData):
    """Class for storing a piece of text and associated metadata."""
    knowledge_base_name: str = Field(
        default="",
        description="knowledge_base_name."
    )
    session_id: str = Field(
        default="",
        description="session_id."
    )
    doc_id: str = Field(
        default="",
        description="ID of the document."
    )
    doc_md5: str = Field(
        default="",
        description="unique document file path md5 value in input_files or input_dir."
    )
    doc_title: str = Field(
        default="",
        description="doc_title."
    )
    root: Optional[DocNode] = Field(
        default=None,
        description="root."
    )
    chunks: List[Chunk] = Field(
        default=[],
        description="chunk content of file."
    )
    """String text."""
    metadata: dict = Field(
        default=dict()
    )
    stream_type: StreamType = Field(
        default=StreamType.REAL
    )
    input_kwargs: dict = Field(
        default=dict(),
        description="input kwargs from Input parameters of the service interface"
    )

    def __init__(self, **kwargs: Any) -> None:
        """Pass page_content in as positional or named arg."""
        super().__init__(**kwargs)

    @classmethod
    def tree_from_nodes(cls, nodes: List[DocNode]):
        """Construct docnodes tree"""
        nodes_text = ""
        if len(nodes) == 1:
            for cnt in nodes[0].content:
                nodes_text += cnt.to_string()
            if len(nodes_text.strip()) == 0:
                raise ProcessorException(ErrorCode.EMPTY_FILE, "No file content parsed.")

        node_stack = [nodes[0]]
        for i, node in enumerate(nodes):
            # parent and children
            if i != 0:
                while node.title_level <= node_stack[-1].title_level:
                    node_stack.pop()
                node.parent = node_stack[-1]
                node_stack[-1].children.append(node)
                node_stack.append(node)
            cls.merge_continuous_text_content(node)

        return nodes

    @classmethod
    def merge_continuous_text_content(cls, node):
        """merge continuous text content"""
        merge_content = []
        if node.content:
            txt_cnt = []
            for c, ele in enumerate(node.content):
                if isinstance(ele, TextContent):
                    txt_cnt.append(ele.to_string())
                if isinstance(ele, TableContent):
                    merge_content.append(TextContent(content='\n'.join(txt_cnt))) if txt_cnt else merge_content
                    merge_content.append(ele)
                    txt_cnt = []
                    continue
                if c == len(node.content) - 1:
                    merge_content.append(TextContent(content='\n'.join(txt_cnt)))
            node.content = merge_content

    def get_knowledge_base_name(self) -> str:
        """get knowledge_base_name"""
        return self.knowledge_base_name

    def get_session_id(self) -> str:
        """get session_id"""
        return self.session_id

    def get_doc_id(self) -> str:
        """Get document id"""
        return self.doc_id

    def get_doc_md5(self) -> str:
        """Get document md5"""
        return self.doc_md5

    def get_doc_title(self) -> str:
        """get doc_title"""
        return self.doc_title

    def get_root(self) -> DocNode:
        """get root"""
        return self.root

    def get_chunks(self) -> List[Chunk]:
        """get chunks"""
        return self.chunks

    def get_metadata(self) -> dict:
        """get metadata"""
        return self.metadata

    def get_stream_type(self) -> StreamType:
        """get stream_type"""
        return self.stream_type

    def set_doc_id(self, doc_id: str) -> None:
        """Set document id"""
        self.doc_id = doc_id

    def set_doc_md5(self, doc_md5: str) -> None:
        """Set document md5"""
        self.doc_md5 = doc_md5

    def set_doc_title(self, doc_title: str) -> None:
        """Set document title"""
        self.doc_title = doc_title

    def set_root(self, root: DocNode) -> None:
        """Set root"""
        self.root = root

    def set_chunks(self, chunks: List[Chunk]) -> None:
        """Set chunks"""
        self.chunks = chunks

    def set_metadata(self, metadata: dict) -> None:
        """Set metadata"""
        self.metadata = metadata

    def get_input_kwargs(self) -> dict:
        """Get input_kwargs"""
        return self.input_kwargs

    def get_input_kwarg_with_key(self, key):
        """Get input_kwarg"""
        return self.input_kwargs.get(key, None)

    def update_input_kwargs(self, kwargs_name: str, value: Any) -> None:
        """update input_kwargs value"""
        self.input_kwargs[kwargs_name] = value

    def update_input_kwargs_dict(self, input_dict: Dict) -> None:
        """update input_kwargs value"""
        self.input_kwargs.update(input_dict)


class DocContext(Context):
    """Document Context"""

    documents: List[Document] = Field(
        default=[],
        description="documents processed in pipeline"
    )
    id2name: dict = Field(
        default=dict(),
        description="file id to file name dict"
    )

    def get_id2name(self) -> dict:
        """Get id2name"""
        return self.id2name

    def set_id2name(self, id2name: dict) -> None:
        """Set id2name"""
        self.id2name = id2name

    def update_id2name(self, doc_id: str, name: str) -> None:
        """Update id2name value"""
        self.id2name[doc_id] = name

    def get_documents(self) -> List[Document]:
        """Get documents"""
        return self.documents

    def set_documents(self, documents: List[Document]) -> None:
        """Set documents"""
        # 将context的input_kwargs透传给document的input_kwargs
        for document in documents:
            document.update_input_kwargs_dict(self.get_input_kwargs())
        self.documents = documents

    def add_documents(self, document: Document) -> None:
        """add document to documents"""
        document.update_input_kwargs_dict(self.get_input_kwargs())
        self.documents.append(document)

    def get_documents_count(self) -> int:
        """count documents num"""
        if self.documents:
            return len(self.documents)
        return 0

    def set_file_count(self, file_count: int) -> None:
        """Set response total file count"""
        self.pipeline_response[FILES_TOTAL_COUNT] = file_count if file_count >= 0 else 0

    def get_file_count(self) -> int:
        """Get file count"""
        return self.pipeline_response.get(FILES_TOTAL_COUNT, 0)

    def set_success_count(self, success_count: int) -> None:
        """Set response total success count"""
        self.pipeline_response["success_count"] = success_count if success_count >= 0 else 0

    def get_fail_documents(self) -> dict:
        """Get response total fail documents"""
        return self.pipeline_response["fail_documents"]

    def set_fail_documents(self, fail_documents: Any) -> None:
        """Set response total fail documents"""
        self.pipeline_response["fail_documents"] = fail_documents

    def to_dict(self) -> dict:
        """context to dict"""
        return {"verbose": self.verbose,
                "component_info": self.component_info,
                "documents": self.documents,
                "id2name": self.id2name,
                "pipeline_response": self.pipeline_response}
