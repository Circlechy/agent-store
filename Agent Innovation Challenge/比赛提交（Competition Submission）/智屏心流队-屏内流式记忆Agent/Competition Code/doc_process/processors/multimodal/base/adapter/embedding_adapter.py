#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 版权所有 (c) 华为技术有限公司 2012-2024

"""EmbeddingAdapter"""
from abc import ABC, abstractmethod
from typing import Any, List

from doc_process.utils.error_code import ProcessorException, ErrorCode


class TextEmbeddingAdapter(ABC):
    """TextEmbeddingAdapter"""

    def check_output(self, batch_embeddings_res: (bool, List[List[List[float]]])):
        """check adapter output"""
        if not self.check_type(batch_embeddings_res):
            raise ProcessorException(
                ErrorCode.TYPE_ERROR,
                "embedding adapter result type incorrect,should be (bool, List[List[List[float]]])."
                "batch_embeddings_res={}".format(batch_embeddings_res)
            )

    def check_type(self, batch_embeddings_res: (bool, List[List[List[float]]])):
        """check type"""
        if isinstance(batch_embeddings_res, tuple) and len(batch_embeddings_res) == 2:
            flag = batch_embeddings_res[0]
            batch_embeddings = batch_embeddings_res[1]

            if isinstance(flag, bool) and isinstance(batch_embeddings, list):
                if batch_embeddings:
                    field_embeddings = batch_embeddings[0]
                    return isinstance(field_embeddings, list)
                return True
        return False

    def check_embeddings(self, field_embeddings):
        """check embedding"""
        if isinstance(field_embeddings, list) and field_embeddings:
            clip_embedding = field_embeddings[0]
            return isinstance(clip_embedding, list)
        return False

    def text_embedding(self, texts: List[str], **kwargs: Any) -> (bool, List[List[List[float]]]):
        """ text_embedding """
        embedding_res = self._text_embedding(texts, **kwargs)
        self.check_output(embedding_res)
        return embedding_res

    @abstractmethod
    def _text_embedding(self, texts: List[str], **kwargs: Any) -> (bool, List[List[List[float]]]):
        """
        text embedding
        Args:
            texts: 需要进行语义表征的文本列表
            kwargs: 关键字参数
        Return:
            Tuple类型
            第一个元素：语义表征服务返回值状态码解析状态，true表示成功，false表示失败
            第二个元素：文本列表的语义表征列表，其中每个本文可能会在语义服务中被切分，它的语义表征结果是个二维的float list
        """
        ...


class ImageEmbeddingAdapter(ABC):
    """ImageEmbeddingAdapter"""

    def image_embedding(self, bytes_list: List[bytes], **kwargs: Any) -> List[Any]:
        """ image_embedding """
        embedding_res = self._image_embedding(bytes_list, **kwargs)
        return embedding_res

    @abstractmethod
    def _image_embedding(self, bytes_list: List[bytes], **kwargs: Any) -> List[Any]:
        """
        image embedding
        """


class AudioEmbeddingAdapter(ABC):
    """AudioEmbeddingAdapter"""

    def audio_embedding(self, bytes_list: List[bytes], **kwargs: Any) -> List[Any]:
        """ audio_embedding """
        embedding_res = self._audio_embedding(bytes_list, **kwargs)
        return embedding_res

    @abstractmethod
    def _audio_embedding(self, bytes_list: List[bytes], **kwargs: Any) -> List[Any]:
        """
        audio embedding
        """
