from enum import Enum


class EmbeddingName(Enum):
    VIDEO_EMBEDDINGS = "vedio_embeddings",
    AUDIO_EMBEDDINGS = "audio_embeddings",
    SPEECH_EMBEDDINGS = "speech_embeddings",
    CAPTION_EMBEDDINGS = "caption_embeddings",


class TextualName(Enum):
    VIDEO_SNIPPED_TEXTUAL = "video_snipped_textual",
    VIDEO_SHORT_TERM_TEXTUAL = "video_short_term_textual",
    VIDEO_LONG_TERM_TEXTUAL = "video_long_term_textual",


short_term_index_schema = {
    "id": "",
    "start_time": "",
    "end_time": "",
    "scene_id": "",
    "scene_catogery": [
    ],
    "caption": "",
    "metadata": {
    },
    "detail": [
        {
            "category": "",
            "ocr": "",
            "location": "",
            "caption": "",
            "metadata": {
            }
        }
    ]
}

long_term_index_schema = {
    "id": "",
    "start_time": "",
    "end_time": "",
    "scene_id": "",
    "scene_catogery": [],
    "location": [],
    "people": [],
    "caption": "",
    "metadata": {}
}
