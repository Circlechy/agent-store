# scene
from enum import Enum

# scene
CORPUS_FAQ = "corpus_faq"
CORPUS_TEXT2IMAGE = "corpus_text2image"


class Scene(Enum):
    RAG = "rag"
    RAG_LOCAL = "rag_local"
    FAQ = "faq"
    T2I = "t2i"
    GUOZIWEI = "guoziwei"
    RAG_DELETE = "rag_delete"


DEFAULT_SCENE = Scene.RAG_LOCAL.value
# loader

# parser

# splitter

# summary

# bm25

# embedding

# export
RESULT_NUM = 10000
