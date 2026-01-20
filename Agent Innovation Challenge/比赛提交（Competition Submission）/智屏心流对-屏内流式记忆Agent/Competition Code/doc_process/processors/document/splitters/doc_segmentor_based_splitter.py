# -*- coding: utf-8 -*-
# Copyright (c) huawei, Inc. and its affiliates.
""" Module providing SegmentorBasedSplitter for Document split (to chunks) """
from abc import abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from doc_process.config_repository.config import merge_internal_config

from doc_process.processors.base.splitters.base import BaseSplitter
from doc_process.processors.document.splitters.util import SEGMENTOR_CLS, TextSegmentor
from doc_process.utils import logging
from doc_process.context.base_schema import Context, ProcessorName
from doc_process.context.doc_schema import Document, Chunk, DocNode, TextContent, ChunkType, TableContent, ImageContent
from doc_process.utils.check_utils import CheckUtils
from doc_process.utils.data_util import generate_id
from doc_process.utils.error_code import ErrorCode, ProcessorException
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


class DocumentSegmentorBasedSplitter(BaseSplitter):
    """ Split document to chunks """
    config: Dict[str, object] = Field(
        default_factory=dict,
        description="configuration",
    )

    segmentor: Optional[TextSegmentor] = Field(
        None,
        description="segment string to segments"
    )

    def __init__(self, **kwargs):
        logger.info("Splitter: {} init start.".format(self.__class__.__name__))
        super(DocumentSegmentorBasedSplitter, self).__init__(**kwargs)
        CheckUtils.check_type(self.config, dict, "config")
        self.config = merge_internal_config(self.config)
        self.config = self.config.get("splitter", {})
        self.check_cfg(self.config)
        segmentor_type = self.config.get("type")
        if segmentor_type not in SEGMENTOR_CLS:
            raise ProcessorException(ErrorCode.VALUE_ERROR,
                                     "Segmentor type {} not supported.".format(segmentor_type))
        segmentor_cls = SEGMENTOR_CLS.get(segmentor_type)
        self.segmentor = segmentor_cls(self.config)
        logger.info("Splitter: {} init done.".format(self.__class__.__name__))

    @classmethod
    def check_cfg(cls, config):
        """ check config """
        CheckUtils.check_type(config, dict, "config")

        CheckUtils.check_key(config, "is_need_segment", "splitter.is_need_segment")
        CheckUtils.check_type(config.get("is_need_segment"), bool, "splitter.is_need_segment")

        CheckUtils.check_key(config, "type", "splitter.type")
        type_ = config.get("type")
        if type_ not in SEGMENTOR_CLS:
            raise ProcessorException(ErrorCode.VALUE_ERROR,
                                     "Splitter type should be in {}".format(list(SEGMENTOR_CLS.keys())))

        CheckUtils.check_key(config, "target_length", "splitter.target_length")
        target_length = config.get("target_length")
        CheckUtils.check_type(target_length, int, "splitter.target_length")
        CheckUtils.check_range(target_length, min_open=0)

        CheckUtils.check_key(config, "overlap_ratio", "splitter.overlap_ratio")
        overlap_ratio = config.get("overlap_ratio")
        CheckUtils.check_types(overlap_ratio, [int, float], "splitter.overlap_ratio")
        CheckUtils.check_range(overlap_ratio, min_close=0, max_open=1)

        if type_ == "punc":
            CheckUtils.check_key(config, "en_segment_puncs", "splitter.en_segment_puncs")
            CheckUtils.check_key(config, "zh_segment_puncs", "splitter.zh_segment_puncs")
            CheckUtils.check_type(config.get("en_segment_puncs"), str, "splitter.en_segment_puncs")
            CheckUtils.check_type(config.get("zh_segment_puncs"), str, "splitter.zh_segment_puncs")

    @abstractmethod
    def _split_one_document(self, document: Document):
        """split one document"""
        ...

    def _split(self, context: Context, **kwargs: Any):
        """split documents"""
        documents = context.get_documents()
        if not documents:
            return
        for document in documents:
            try:
                chunks = self._split_one_document(document)
                if document.chunks:
                    document.chunks += chunks
                else:
                    document.chunks = chunks
                logger.debug("Document {} split to {} chunks.".format(document.doc_title, len(chunks)))
                logger.debug(
                    "doc_id={},chunk_id={}".format(document.doc_id, [chunk.chunk_id for chunk in document.chunks])
                )
            except Exception as ex:
                msg = "Document {} split fail, error_msg={}".format(document.doc_title, str(ex))
                context.add_info_to_component(ProcessorName.SPLITTER, document.get_doc_md5(),
                                              ex if isinstance(ex, ProcessorException) else ProcessorException(
                                                  ErrorCode.SPLITTER_ERROR, msg)
                                              )
                logger.error(msg)
        total_chunk_num = sum([len(document.chunks) for document in documents])
        logger.info("{} documents split to {} chunks.".format(len(documents), total_chunk_num))

    def _update_neighbor_chunk_id(self, chunks: List[Chunk]):
        """ update 'prev_chunk_id' and 'next_chunk_id' """
        if len(chunks) <= 0:
            return
        # update prev_chunk_id
        for i, chunk in enumerate(chunks):
            if i == 0:
                continue
            chunk.chunk_metadata["prev_chunk_id"] = chunks[i - 1].chunk_id

        # update next_chunk_id
        for i, chunk in enumerate(chunks):
            if i == len(chunks) - 1:
                continue
            chunk.chunk_metadata["next_chunk_id"] = chunks[i + 1].chunk_id


class PlainSplitter(DocumentSegmentorBasedSplitter):
    """ Split document as plain text """

    def _split_one_document(self, document: Document):
        """split one document"""
        nodes = document.root.flat_with_children()
        node_texts, need_segment = [], []
        # segment texts
        for i, node in enumerate(nodes):
            if node.chapter is None:
                continue
            if len(node.chapter) > 0 and i != 0:  # skip doc_title
                need_segment.append(False)  # 标题不进行切分
                node_texts.append(node.chapter[-1])
            for content_ele in node.content:
                if isinstance(content_ele, TextContent):
                    need_segment.append(True)  # 切分文本类型
                else:
                    need_segment.append(False)  # 表格、图片等类型不切分
                node_texts.append(content_ele.to_string())
        # 是否切分
        if not self.config.get("is_need_segment", True):
            chunk_texts = ["\n".join(node_texts)]
        else:
            chunk_texts = self.segmentor.segment(list(zip(node_texts, need_segment)))

        # construct chunks
        chunks = []
        for chunk_text in chunk_texts:
            chunk = Chunk(
                doc_node_id="",
                chunk_id=generate_id(document.knowledge_base_name, document.session_id, "", chunk_text),
                chapter=[Path(document.doc_title).stem],
                content=TextContent(content=chunk_text),
                chunk_type=ChunkType.TEXTCONTENT,
                index_info=None
            )
            chunks.append(chunk)
        self._update_neighbor_chunk_id(chunks)
        return chunks


class ParaSplitter(DocumentSegmentorBasedSplitter):
    """ Split document based on structure information"""

    @classmethod
    def add_chapter_to_empty_content(cls, nodes):
        """node的content没有字符且children为空（chunk会被删除），添加chapter信息作为内容"""
        for node in nodes:
            node_text = ""
            for cnt in node.content:
                node_text += cnt.to_string()

            if not node_text.strip() and not node.children:
                node.content.append(TextContent(content=' '.join(node.chapter[1:])))

    def _split_one_node(self, node: DocNode, document: Document):
        """ split one node of document to chunks """
        chunks = []
        chapter = [node.chapter[-1]] if document.doc_title.endswith('.xlsx') and node.chapter else node.chapter
        if not chapter:
            return []

        # 不切分, ppt文档单页为一个chunk, faq单行为一个chunk
        if (document.metadata.get("parse_context", {}).get("p_type") == "ppt"
                or document.metadata.get("parse_context", {}).get("p_type") == "faq"
                or not self.config.get("is_need_segment", True)):
            return self._disable_segment_chunk(chapter, document, node)

        for content_ele in node.content:
            if isinstance(content_ele, TextContent):
                chunk_texts = self.segmentor.segment(content_ele.to_string())
                for chunk_text in chunk_texts:
                    chunk = Chunk(
                        doc_node_id=node.id,
                        chunk_id=generate_id(
                            document.knowledge_base_name, document.session_id, " ".join(chapter), chunk_text),
                        chapter=chapter,
                        content=TextContent(content=chunk_text),
                        chunk_type=ChunkType.TEXTCONTENT,
                        index_info=None
                    )
                    chunks.append(chunk)
            else:
                if isinstance(content_ele, TableContent):
                    chunk_type = ChunkType.TABLECONTENT
                elif isinstance(content_ele, ImageContent):
                    chunk_type = ChunkType.PICTURECONTENT
                else:
                    raise ProcessorException(ErrorCode.SPLITTER_ERROR,
                                             "Unrecognizable content type {}".format(type(content_ele)))
                if not content_ele.to_string().strip():
                    continue

                chunk = Chunk(
                    doc_node_id=node.id,
                    chunk_id=generate_id(
                        document.knowledge_base_name, document.session_id, " ".join(chapter), content_ele.to_string()),
                    chapter=chapter,
                    content=content_ele,
                    chunk_type=chunk_type,
                    index_info=None
                )
                chunks.append(chunk)
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        for chunk in chunks:
            chunk.chunk_metadata["chunk_ids"] = chunk_ids
        return chunks

    def _disable_segment_chunk(self, chapter, document, node):
        """ Disable segment to content under a chapter """
        chunk_text = "\n".join([content_ele.to_string() for content_ele in node.content])
        if not chunk_text:
            return []
        chunk_id = generate_id(document.knowledge_base_name, document.session_id, " ".join(chapter), chunk_text)
        chunk = Chunk(
            doc_node_id=node.id,
            chunk_id=chunk_id,
            chapter=chapter,
            content=TextContent(content=chunk_text),
            chunk_type=ChunkType.TEXTCONTENT,
            index_info=None
        )
        chunk.chunk_metadata["chunk_ids"] = [chunk_id]
        return [chunk]

    def _split_one_document(self, document: Document):
        """split one document"""
        nodes = document.root.flat_with_children()
        self.add_chapter_to_empty_content(nodes)
        chunks = []
        for node in nodes:
            chunks.extend(self._split_one_node(node, document))
        self._update_neighbor_chunk_id(chunks)
        return chunks
