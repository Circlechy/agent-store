#  Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.

"""
StructureSummaryAdapter
"""

from abc import ABC, abstractmethod
from typing import Any

from doc_process.utils.error_code import ProcessorException, ErrorCode


class StructureSummaryAdapter(ABC):
    """
    StructureSummaryAdapter: abstract
    """

    def check_output(self, summary: str):
        """check if the result of adapter is valid."""
        if not isinstance(summary, str):
            raise ProcessorException(ErrorCode.TYPE_ERROR,
                                     "Type of summary should be str, is {} now.".format(type(summary)))

    def forward(self, doc_title: str, chapter_title: str, content: str, **kwargs: Any) -> str:
        """adapter main function, use adapter.forward(**kwargs)"""
        summary_content = self._forward(doc_title=doc_title, chapter_title=chapter_title, content=content, **kwargs)
        self.check_output(summary_content)
        return summary_content

    @abstractmethod
    def _forward(self, doc_title: str, chapter_title: str, content: str, **kwargs: Any) -> str:
        """ generate summaries based on doc_title/chapter_title/content, return the summary content. """
        ...
