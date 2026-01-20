#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024
"""ErrorCode"""
from enum import Enum

from doc_process.utils import logging

logger = logging.get_logger()


class ErrorCode(Enum):
    """ErrorCode"""
    # General errors
    SUCCESS = (0, "Success.")
    FAILURE = (-1, "Failed.")
    PARAM_INVALID = (-2, "Input parameter error.")
    CONFIG_INVALID = (-3, "Input config error.")
    OBJECT_NOT_EXIST = (-4, "Object not exist.")
    INTERNAL_ERROR = (-5, "Server internal error")
    UNMATCH_ERROR = (-6, "Unmatch error")
    FORMAT_ERROR = (-7, "Format error")
    FILE_INVALID = (-8, "File invalid")
    CONTENT_INVALID = (-9, "Content invalid")
    FILE_ACCESS_EXP = (-10, "File access permission error")
    NETWORK_REQUEST_ERROR = (-11, "Network request error")
    INITIALIZE_ERROR = (-12, "Server initialize error.")
    TIMEOUT = (-14, "Timeout.")
    BAD_STATE = (-15, "Bad State.")
    INTENT_INVOKE_ERROR = (-16, "Intent Service Invoke Failed.")
    CALL_THIRD_ERROR = (-17, "Call third Error.")
    RES_NOT_FOUND_ERROR = (-18, "Resource not found Error.")
    IO_ERROR = (-19, "IO Error.")
    AUTH_ERROR = (-20, "AUTH Error.")
    PARSING_ERROR = (-21, "Parsing Error")
    JSON_SYNTAX_ERROR = (-22, "Json syntax error.")
    TYPE_ERROR = (-23, "Param type error.")
    ATTRIBUTE_ERROR = (-24, "Attribute not found.")
    VALUE_ERROR = (-25, "Inappropriate argument value")
    IMPORT_ERROR = (-26, "Import error.")
    NOT_IMPLEMENTED_ERROR = (-27, "NotImplementedError")

    # Loader errors
    INVALID_FILE_PATH = (-1001, "Invalid file path or file does not exist.")
    UNSUPPORTED_FILE_FORMAT = (-1002, "Unsupported file format.")
    FILE_READ_ERROR = (-1003, "Error reading file due to permissions or encoding issues.")
    LOADER_FAILURE = (-1004, "Failed to load the document.")

    # parser errors
    PARSER_ERROR = (-2001, "Error parsing document content.")
    INVALID_DOCUMENT_STRUCTURE = (-2002, "Document structure is invalid or corrupted.")
    EMPTY_FILE = (-2003, "The file is empty or contains no valid data.")
    FILE_TOO_LARGE = (-2004, "The file size exceeds the allowed limit.")
    PARSER_PARAM_INVALID = (-2005, "Parser Input parameter error.")

    # Paragraph Splitter errors
    SPLITTER_ERROR = (-3001, "Failed to split paragraphs from the document.")
    SPLITTER_PARAM_INVALID = (-3002, "Splitter Input parameter error.")

    # Structure Summary Extractor errors
    SUMMARY_EXTRACTION_ERROR = (-4001, "extract summary chunk fail")
    SUMMARY_GENERATE_ERROR = (-4002, "generate summary chunk fail")
    SUMMARY_GENERATE_METADATA_ERROR = (-4003, "generate chunk_metadata fail.")
    EXTRACTOR_PARAM_INVALID = (-4004, "Extractor Input parameter error.")

    # BM25 errors
    BM25_ERROR = (-5001, "Error BM25.")
    BM25_PARAM_INVALID = (-5002, "BM25 Input parameter error.")

    # Embedding errors
    EMBEDDING_ERROR = (-6001, "Error Embedding.")
    EMBEDDING_PARAM_INVALID = (-6002, "Embedding Input parameter error.")

    # Export Falcon errors
    EXPORT_ERROR = (-7001, "Error Export.")
    EXPORT_ES_ERROR = (-7002, "Error Export to es.")
    EXPORT_VS_ERROR = (-7003, "Error Export to vs.")
    EXPORT_FALCON_ERROR = (-7004, "Error Export to falcon.")
    EXPORT_PARAM_INVALID = (-7005, "Export Input parameter error.")

    # Delete Falcon errors
    DELETE_ERROR = (-8001, "Error Delete.")
    DELETE_ES_ERROR = (-8002, "Error Delete from es.")
    DELETE_VS_ERROR = (-8003, "Error Delete from vs.")
    DELETE_FALCON_ERROR = (-8004, "Error Delete from falcon.")
    DELETE_PARAM_INVALID = (-8005, "Delete Input parameter error.")

    def __str__(self):
        return "ErrorCode: ({}, {})".format(self.code(), self.message())

    def code(self):
        """Returns the error code."""
        return self.value[0]

    def message(self):
        """Returns the error message."""
        return self.value[1]


class ProcessorException(Exception):
    """
    Base exception class for RAG knowledge processing.
    """

    def __init__(self, error_code: ErrorCode, message=None):
        if isinstance(error_code, ErrorCode) and message:
            self.error_code = error_code
            self.message = str(message)
        elif message:
            self.error_code = ErrorCode.SUCCESS
            self.message = str(error_code) + str(message)
        else:
            self.error_code = ErrorCode.SUCCESS
            self.message = self.error_code.message()
        super().__init__(self.message)

    def __str__(self):
        return f"{self.error_code} : {self.message}"

    def get_error_code(self) -> ErrorCode:
        """Returns the error code."""
        return self.error_code

    def get_message(self) -> str:
        """Returns the error message."""
        return self.message
