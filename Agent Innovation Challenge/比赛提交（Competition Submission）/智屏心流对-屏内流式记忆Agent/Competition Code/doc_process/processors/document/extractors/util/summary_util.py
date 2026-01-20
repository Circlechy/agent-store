#   Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

"""
summary util
"""
from typing import List

import tqdm

from doc_process.processors.base.adapter.summary_adapter import StructureSummaryAdapter
from doc_process.utils import logging
from doc_process.context.doc_schema import ChunkType, Chunk, TextContent, SummaryTree, Document, SummaryForest
from doc_process.context.doc_constants import DEFAULT_SUMMARY_TARGET_LENGTH
from doc_process.utils.data_util import is_valid_generated_content, generate_id

logger = logging.get_logger()


def build_summary_forest(documents: List[Document], summary_forest: SummaryForest, tqdm_display: bool = True):
    """build_summary_forest"""
    for document in tqdm.tqdm(documents, desc="Parse input documents", disable=tqdm_display):
        try:
            doc_title = document.doc_title
            knowledge_base_name = document.knowledge_base_name
            doc_root_node = document.root
            summary_tree = SummaryTree.from_doc_root_node(doc_root_node=doc_root_node, doc_title=doc_title,
                                                          knowledge_base_name=knowledge_base_name)
            summary_forest.update(summary_tree)
        except Exception as e:
            logger.error(f"document {document.doc_title} build summary_tree fail. {e}")


def add_summaries_to_chunk_metadata(document: Document, summary_forest: SummaryForest, tqdm_display: bool = True):
    """add_summaries_to_chunk_metadata"""
    doc_title = document.doc_title
    chunks = document.chunks if document.chunks is not None else []
    summary_tree = summary_forest.get(doc_title)
    for chunk in tqdm.tqdm(chunks, desc="Generate summary Meta-data for each chunk in the document",
                           disable=tqdm_display):
        node = summary_tree.get_chapter_node(chunk.chapter)
        chapter_summary = node.node_summary if node is not None else ""
        chunk.set_chapter_summary(chapter_summary)

        parent_node = summary_tree.get_chapter_node(chunk.chapter[:-1])
        parent_chapter_summary = parent_node.node_summary if parent_node is not None else ""
        chunk.chunk_metadata.setdefault("parent_chapter_summary", parent_chapter_summary)


def build_generated_summary_chunk(document: Document, summary_forest: SummaryForest,
                                  adapter: StructureSummaryAdapter = None,
                                  target_length: int = DEFAULT_SUMMARY_TARGET_LENGTH, tqdm_display: bool = True):
    """build_generated_summary_chunk"""
    if adapter is None:
        return
    knowledge_base_name = document.knowledge_base_name
    new_generated_summary_chunk = []
    summary_tree = summary_forest.get(document.doc_title)
    for node in tqdm.tqdm(
        summary_tree.chapter_tree, desc="Generate abstractive summaries chunks for each node in the tree",
        disable=tqdm_display
    ):
        if node.children_chapter is None or len(node.children_chapter) == 0:
            continue
        chunk_chapter = node.current_chapter
        chunk_content = adapter.forward(
            doc_title=document.doc_title, chapter_title="，".join(chunk_chapter), content=node.node_summary
        )
        chunk_content = chunk_content[:target_length]
        if len(chunk_content.strip()) == 0 or (not is_valid_generated_content(chunk_content)):
            continue
        text_content = TextContent(content=chunk_content)
        chunk_id = generate_id(knowledge_base_name=knowledge_base_name, session_id=document.session_id,
                               title=" ".join(chunk_chapter),
                               content=text_content.to_string())
        new_chunk = Chunk(doc_node_id="", chunk_id=chunk_id, chapter=chunk_chapter, content=text_content,
                          chunk_type=ChunkType.SUMMARY)
        new_generated_summary_chunk.append(new_chunk)
    if document.chunks:
        document.chunks.extend(new_generated_summary_chunk)
    else:
        document.chunks = new_generated_summary_chunk


def build_extracted_summary_chunk(document: Document, summary_forest: SummaryForest,
                                  target_length: int = DEFAULT_SUMMARY_TARGET_LENGTH, tqdm_display: bool = True):
    """build_extracted_summary_chunk"""
    knowledge_base_name = document.knowledge_base_name
    new_extracted_summary_chunk = []
    summary_tree = summary_forest.get(document.doc_title)
    for node in tqdm.tqdm(
        summary_tree.chapter_tree,
        desc="Generate extractive summaries chunks for each node in the tree",
        disable=tqdm_display
    ):
        if node.children_chapter is None or len(node.children_chapter) == 0:
            continue
        chunk_content = node.node_summary[:target_length]
        if len(chunk_content.strip()) == 0 or (not is_valid_generated_content(chunk_content)):
            continue
        chunk_chapter = node.current_chapter
        text_content = TextContent(content=chunk_content)
        chunk_id = generate_id(knowledge_base_name=knowledge_base_name, session_id=document.session_id,
                               title=" ".join(chunk_chapter),
                               content=text_content.to_string())
        new_chunk = Chunk(doc_node_id="", chunk_id=chunk_id, chapter=chunk_chapter, content=text_content,
                          chunk_type=ChunkType.SUMMARY)
        new_extracted_summary_chunk.append(new_chunk)
    if document.chunks:
        document.chunks.extend(new_extracted_summary_chunk)
    else:
        document.chunks = new_extracted_summary_chunk
