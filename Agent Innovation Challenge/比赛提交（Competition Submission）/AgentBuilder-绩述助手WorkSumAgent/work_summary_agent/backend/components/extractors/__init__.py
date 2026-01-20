# -*- coding: utf-8 -*-
"""提取器组件"""

from .text_extractor import TextExtractorComponent
from .document_extractor import DocumentExtractorComponent
from .image_extractor import ImageExtractorComponent
from .text_merger import TextMergerComponent

__all__ = [
    'TextExtractorComponent',
    'DocumentExtractorComponent',
    'ImageExtractorComponent',
    'TextMergerComponent',
]
