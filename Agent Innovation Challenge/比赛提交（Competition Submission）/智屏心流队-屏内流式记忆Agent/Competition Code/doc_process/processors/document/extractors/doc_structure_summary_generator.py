#   Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

"""
StructureSummaryExtractor
"""
from collections import defaultdict
from typing import List, Any, Optional, Dict

import tqdm
from doc_process.config_repository.config import merge_internal_config

from doc_process.processors.base.adapter.summary_adapter import StructureSummaryAdapter
from doc_process.processors.base.extractors.base import BaseSummaryExtractor
from doc_process.processors.document.extractors.util.summary_util import build_extracted_summary_chunk, \
    build_generated_summary_chunk, add_summaries_to_chunk_metadata, build_summary_forest
from doc_process.utils import logging
from doc_process.context.doc_schema import Document, SummaryForest, Context
from doc_process.utils.check_utils import CheckUtils
from doc_process.context.doc_constants import ProcessorName, IS_EXTRACTED_SUMMARY_CHUNK, IS_GENERATED_SUMMARY_CHUNK, \
    IS_ADD_METADATA, SUMMARY_TARGET_LENGTH, DEFAULT_SUMMARY_TARGET_LENGTH
from doc_process.utils.data_util import check_xlsx_document
from doc_process.utils.error_code import ProcessorException, ErrorCode
from doc_process.utils.pydantic import Field

logger = logging.get_logger()


class DocumentStructureSummaryExtractor(BaseSummaryExtractor):
    """
    Extract summary from document based on the article structure.
    It receives the Document list objects built by the pipeline's parsing module.
    The specific summary generator subclass needs to inherit its base class and
    implement the specific abstract generation method in the summary function.

    """
    config: Dict[str, object] = Field(
        default_factory=dict,
        description="configuration.",
    )
    adapter: Optional[StructureSummaryAdapter] = Field(
        default=None,
        description="Summary adapter. Support for user customization",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        self._parse_config()

    def add_summary_metadata(self, detail_info: dict, documents: List[Document], summary_forest: SummaryForest,
                             tqdm_display: bool = True):
        """add_summary_metadata"""
        if self.config.get(IS_ADD_METADATA):
            for document in tqdm.tqdm(documents, desc="Generate summary Meta-data for documents", disable=tqdm_display):
                try:
                    add_summaries_to_chunk_metadata(document, summary_forest, tqdm_display)
                except Exception as e:
                    detail_info[document.get_doc_md5()] = ProcessorException(ErrorCode.SUMMARY_GENERATE_METADATA_ERROR,
                                                                      f"generate chunk_metadata fail, {e}")
                    logger.error(f"Document {document.doc_title} generate chunk_metadata fail, {e}")
            logger.debug("Extractor: StructureSummaryExtractor generate chunk_metadata done.")

    def generate_summary_chunk(self, detail_info: dict, documents: List[Document], summary_forest: SummaryForest,
                               tqdm_display: bool = True) -> dict:
        """generate_summary_chunk"""
        target_length = self.config.get(SUMMARY_TARGET_LENGTH, DEFAULT_SUMMARY_TARGET_LENGTH)
        chunk_num_update = defaultdict(int)
        if self.config.get(IS_EXTRACTED_SUMMARY_CHUNK):  # Extract Type 1
            for document in tqdm.tqdm(documents, desc="Generate extractive summaries chunks for documents",
                                      disable=tqdm_display):
                try:
                    if check_xlsx_document(document.doc_title):
                        continue
                    chunk_num_base = len(document.chunks) if document.chunks else 0
                    build_extracted_summary_chunk(document, summary_forest, target_length, tqdm_display)
                    chunk_num_new = len(document.chunks) if document.chunks else 0
                    chunk_num_update[document.doc_title] += chunk_num_new - chunk_num_base
                except Exception as e:
                    detail_info[document.get_doc_md5()] = ProcessorException(
                        ErrorCode.SUMMARY_EXTRACTION_ERROR, f"extracted_summary_chunk fail, {e}")
                    logger.error(f"Document {document.doc_title} generate extracted_summary_chunk fail, {e}")
            logger.debug("Extractor: StructureSummaryExtractor generate extracted_summary_chunk done.")
        if self.config.get(IS_GENERATED_SUMMARY_CHUNK) and self.adapter is not None:  # Extract Type 2
            for document in tqdm.tqdm(documents, desc="Generate abstractive summaries chunks for documents",
                                      disable=tqdm_display):
                try:
                    if check_xlsx_document(document.doc_title):
                        continue
                    chunk_num_base = len(document.chunks) if document.chunks else 0
                    build_generated_summary_chunk(document, summary_forest, self.adapter, target_length, tqdm_display)
                    chunk_num_new = len(document.chunks) if document.chunks else 0
                    chunk_num_update[document.doc_title] += chunk_num_new - chunk_num_base
                except Exception as e:
                    detail_info[document.get_doc_md5()] = ProcessorException(
                        ErrorCode.SUMMARY_GENERATE_ERROR, f"generated_summary_chunk fail, {e}")
                    logger.error(f"Document {document.doc_title} generate generated_summary_chunk fail, {e}")
            logger.debug("Extractor: StructureSummaryExtractor generate generated_summary_chunk done.")
        return chunk_num_update

    def _parse_config(self):
        """
        Initialize a StructureSummaryGenerator.

        Args:
            config (Config class parsed from yaml object): a dict including all user configuration items.
                is_add_metadata: Whether to add the Metadata fields about summary for each Chunk in the Document.
                                If True, StructureSummaryGenerator will add `chapter_summary` and
                                `parent_chapter_summary` into Metadata. `chapter_summary` indicates
                                the summary of the chapter where the Chunk is located.
                                `parent_chapter_summary` indicates the summary of the upper level
                                of the chapter where the Chunk is located. Defaults to True.
                is_extracted_summary_chunk: Whether to generate summary content in extraction mode.
                                If True, StructureSummaryGenerator will create several new Chunk objects with
                                the document summary and the chapter summary at each level as the content fields.
                                If so, the number of chunks in the Document object may increase.
                                Defaults to True.
                is_generated_summary_chunk: Whether to generate summary content in abstraction mode with LLM.
                                If True, StructureSummaryGenerator will create several new Chunk objects with
                                the document summary and the chapter summary at each level as the content fields.
                                If so, the number of chunks in the Document object may increase.
                                Defaults to False.
                tqdm_display: Whether to display the progress bar. Defaults to False.

        """
        logger.info("Extractor: StructureSummaryExtractor init start.")
        CheckUtils.check_type(self.config, dict, "config")
        self.config = merge_internal_config(self.config)

        self.config = self.config.get("extractor", {})
        CheckUtils.check_key(self.config, IS_EXTRACTED_SUMMARY_CHUNK, "extractor.is_extracted_summary_chunk")
        CheckUtils.check_key(self.config, IS_GENERATED_SUMMARY_CHUNK, "extractor.is_generated_summary_chunk")
        CheckUtils.check_key(self.config, IS_ADD_METADATA, "extractor.is_add_metadata")
        CheckUtils.check_key(self.config, SUMMARY_TARGET_LENGTH, "extractor.target_length")
        CheckUtils.check_type(self.config.get(IS_EXTRACTED_SUMMARY_CHUNK), bool, "extractor.is_extracted_summary_chunk")
        CheckUtils.check_type(self.config.get(IS_GENERATED_SUMMARY_CHUNK), bool, "extractor.is_generated_summary_chunk")
        CheckUtils.check_type(self.config.get(IS_ADD_METADATA), bool, "extractor.is_add_metadata")
        CheckUtils.check_type(self.config.get(SUMMARY_TARGET_LENGTH), int, "extractor.target_length")

        if self.config.get(IS_GENERATED_SUMMARY_CHUNK):
            if self.adapter is not None and hasattr(self.adapter, "forward"):
                self.adapter = self.adapter
                logger.info("Extractor: StructureSummaryGenerator init done with your customized adapter.")
            else:
                raise ProcessorException(
                    ErrorCode.VALUE_ERROR, "extractor adapter instance is invalid when "
                                           "extractor.is_generated_summary_chunk=True. Check your adapter "
                                           "implement if you inherits StructureSummaryAdapter class. "
                                           "If you don't want to use this features, set "
                                           "extractor.is_generated_summary_chunk=False."
                )
        else:
            self.adapter = None
            logger.debug("Param extractor.is_generated_summary_chunk is False, "
                         "the feature that generating summary with adapter is disabled.")
            logger.info("Extractor: StructureSummaryExtractor init done.")

    def _extract(self, context: Context, **kwargs: Any) -> None:
        """
        Call a summary generation method.
        1. Product a SummaryForest object based on the Document Structure, i.e. DocNode object in Document class.
        2. Generate Summary Chunks with StructureSummaryGenerator when is_extracted_summary_chunk=True.
        3. Generate Summary Chunks with StructureSummaryGenerator when is_generated_summary_chunk=True and
           adapter has been successfully initialized.
        4. Add the Metadata fields about summary for each Chunk.

        Args:
            context: Context including documents (List[Document]): Set of documents to be processed.
        """
        documents: List[Document] = context.get_documents()
        if not documents:
            return

        tqdm_display = not self.config.get("tqdm_display", False)
        summary_forest = SummaryForest(summary_set=dict())
        build_summary_forest(documents, summary_forest, tqdm_display)
        logger.debug("Extractor: StructureSummaryExtractor parse List[Document] done.")
        logger.debug(summary_forest)

        detail_info = dict()
        chunk_num_info = self.generate_summary_chunk(detail_info, documents, summary_forest, tqdm_display)
        self.add_summary_metadata(detail_info, documents, summary_forest, tqdm_display)

        if any(detail_info):
            context.update_component_info(ProcessorName.SUMMARY, detail_info)
        logger.info(
            f"Extractor: StructureSummaryExtractor generate {sum(chunk_num_info.values())} new chunks, Type: SUMMARY")
