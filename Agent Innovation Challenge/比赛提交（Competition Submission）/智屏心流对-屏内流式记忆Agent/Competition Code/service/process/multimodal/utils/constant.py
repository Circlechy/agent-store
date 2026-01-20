# scene
from enum import Enum


class Scene(Enum):
    VIDEO = "vedio"
    AUDIO = "audio"
    IMAGE = "image"


DEFAULT_SCENE = Scene.VIDEO.value


class Strategy(Enum):
    VSTREAM = "Vstream"
    VSTREAM_TEXTUAL = "Vstream_textual"
    QWEN = "qwen"
    QWEN_TEXTUAL = "qwen_textual"
    TEXTUAL = "textual"

UG_INFO = "ug_info"