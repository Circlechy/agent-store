from doc_process.pipeline_manage.pipeline import StreamProcessPipeline
from doc_process.processors.multimodal.base.adapter.embedding_adapter import ImageEmbeddingAdapter
from doc_process.processors.multimodal.base.parallel.base import BaseParallel
from doc_process.processors.multimodal.base.serial.base import BaseSerial
from doc_process.processors.multimodal.embedding.mm_embedding import MultimodalEmbedding
from doc_process.processors.multimodal.export.mm_textual_export import TextualExport
from doc_process.processors.multimodal.export.mm_vector_export import VectorExport
from doc_process.processors.multimodal.recognize.parallel_recognizer import ParallelRecognizer
from doc_process.processors.multimodal.recognize.short_term_recognizer import ShortTermRecognizer
from doc_process.processors.multimodal.recognize.snippet_recognizer import SnippetRecognizer
from doc_process.processors.multimodal.recognize.long_term_recognizer import LongTermRecognizer
from service.process.multimodal.qwen.adapter_impl.image_embedding_adapter_impl import QwenImageEmbeddingAdapterImpl
from service.process.multimodal.qwen.adapter_impl.vector_export_adapter_impl import QwenExportAdapterImpl
from service.process.multimodal.textual.event_detector_impl import ProactivecareDetectorAdapterImpl
from service.process.multimodal.textual.object_detector_impl import SceneInAndOutDetectorAdapterImpl
from service.process.multimodal.textual.scene_detector_impl import FusionSceneDetectorAdapterImpl
from service.process.multimodal.textual.textual_config import DetectType, FOOD_DETECT_STR, PERSONAL_DETECT_STR
from service.process.multimodal.textual.long_term_scene_detector_impl import IntermiSceneDetectorAdapterImpl
from service.process.multimodal.textual.textual_export_adapter_impl import TextualExportAdapterImpl
from service.process.multimodal.utils.constant import Strategy
from service.process.multimodal.vstream.adapter_impl.image_embedding_adapter_impl import \
    VstreamImageEmbeddingAdapterImpl
from service.process.multimodal.vstream.adapter_impl.vector_export_adapter_impl import VstreamVectorExportAdapterImpl

# todo: 6. @xinjiapo
def build_textual_processor(config_dict, **kwargs):
    food_type = DetectType.FOOD.value
    personal_type = DetectType.PERSONAL.value

    food_snippet_recognizer = SnippetRecognizer(
        food_detector=
        SceneInAndOutDetectorAdapterImpl(object_str=FOOD_DETECT_STR, device="cuda:0", **kwargs),
        detect_type=food_type,
        proactive_care_detector=ProactivecareDetectorAdapterImpl(detect_type=food_type, **kwargs)
    )

    personal_snippet_recognizer = SnippetRecognizer(
        personal_detector=
        SceneInAndOutDetectorAdapterImpl(object_str=PERSONAL_DETECT_STR, device="cuda:0", **kwargs),
        detect_type=personal_type
    )

    short_term_recognizer = ShortTermRecognizer(scene_detector=FusionSceneDetectorAdapterImpl(**kwargs))
    # long_term_recognizer = LongTermRecognizer(
    #     event_judgment_detector=EventJudgmentDetectorAdapterImpl(detect_type=food_type, **kwargs))

    snippet_textual_config = config_dict.get("es_short_term")
    short_term_textual_config = config_dict.get("es_short_term")
    long_term_textual_config = config_dict.get("es_long_term")

    snipped_textual_export_adapter_impl = TextualExportAdapterImpl(snippet_textual_config)
    short_term_textual_export_adapter_impl = TextualExportAdapterImpl(short_term_textual_config)
    long_term_textual_export_adapter_impl = TextualExportAdapterImpl(long_term_textual_config)

    snipped_recognizer = ParallelRecognizer(processors=[food_snippet_recognizer, personal_snippet_recognizer])
    textual_recognizer = BaseSerial(processors=[snipped_recognizer, short_term_recognizer])

    # export
    textual_export = TextualExport(snipped_textual_export_adapter=snipped_textual_export_adapter_impl,
                                   short_term_textual_export_adapter=short_term_textual_export_adapter_impl,
                                   long_term_textual_export_adapter=long_term_textual_export_adapter_impl)
    return textual_recognizer, textual_export

def build_event_textual_processor(config_dict, **kwargs):
    long_term_recognizer = LongTermRecognizer(scene_detector=IntermiSceneDetectorAdapterImpl(config_dict,**kwargs))
    textual_recognizer = BaseSerial(processors=[long_term_recognizer])
    return textual_recognizer

def build_vstream_processor(config_dict, **kwargs):
    image_embedding_adapter: ImageEmbeddingAdapter = VstreamImageEmbeddingAdapterImpl(config_dict, **kwargs)
    export_adapter: VstreamVectorExportAdapterImpl = VstreamVectorExportAdapterImpl(config_dict, **kwargs)

    embedding = MultimodalEmbedding(config=config_dict, image_embedding_adapter=image_embedding_adapter)
    vector_export = VectorExport(config=config_dict, export_adapter=export_adapter)
    return embedding, vector_export


class PipelineFactory:
    """PipelineFactory"""

    @staticmethod
    def create_vstream_pipeline(config_dict: dict, **kwargs):
        # only Flash-Vstream 向量化
        embedding, vector_export = build_vstream_processor(config_dict, **kwargs)
        default_pipeline = StreamProcessPipeline(
            name=Strategy.VSTREAM.name,
            processors=[
                embedding,
                vector_export
            ]
        )
        return default_pipeline

    @staticmethod
    def create_vstream_textual_pipeline(config_dict: dict, **kwargs):
        # Flash-Vstream 向量化 + 文本化
        # todo: 改为parallel
        textual_recognizer, textual_export = build_textual_processor(config_dict)
        embedding, vector_export = build_vstream_processor(config_dict, **kwargs)
        default_pipeline = StreamProcessPipeline(
            name=Strategy.VSTREAM_TEXTUAL.name,
            processors=[
                textual_recognizer,
                textual_export,
                embedding,
                vector_export
            ]
        )
        return default_pipeline

    @staticmethod
    def create_qwen_pipeline(config_dict: dict, **kwargs):
        #  向量化
        image_embedding_adapter: QwenImageEmbeddingAdapterImpl = QwenImageEmbeddingAdapterImpl(config_dict, **kwargs)
        vector_export_adapter: QwenExportAdapterImpl = QwenExportAdapterImpl(**kwargs)
        vector_embedding = MultimodalEmbedding(config=config_dict, image_embedding_adapter=image_embedding_adapter)
        vector_export = VectorExport(config=config_dict, export_adapter=vector_export_adapter)
        default_pipeline = StreamProcessPipeline(
            name=Strategy.QWEN_TEXTUAL.name,
            processors=[
                vector_embedding,
                vector_export
            ]
        )
        return default_pipeline

    @staticmethod
    def create_qwen_textual_pipeline(config_dict: dict, **kwargs):
        #  向量化 + 文本化
        textual_recognizer, textual_export = build_textual_processor(config_dict, **kwargs)
        image_embedding_adapter: QwenImageEmbeddingAdapterImpl = QwenImageEmbeddingAdapterImpl(config_dict, **kwargs)
        vector_export_adapter: QwenExportAdapterImpl = QwenExportAdapterImpl(config_dict, **kwargs)
        vector_embedding = MultimodalEmbedding(config=config_dict, image_embedding_adapter=image_embedding_adapter)
        vector_export = VectorExport(config=config_dict, export_adapter=vector_export_adapter)
        # todo: 改为parallel
        default_pipeline = StreamProcessPipeline(
            name=Strategy.QWEN_TEXTUAL.name,
            processors=[
                # textual_recognizer,
                # textual_export,
                BaseParallel(processors=[BaseSerial(processors=[textual_recognizer, textual_export]),
                                         BaseSerial(processors=[vector_embedding, vector_export])])
            ]
        )
        return default_pipeline

    @staticmethod
    def create_qwen_event_textual_pipeline(config_dict: dict, **kwargs):
        #  向量化 + 文本化
        textual_recognizer, textual_export = build_textual_processor(config_dict, **kwargs)
        event_textual_recognizer = build_event_textual_processor(config_dict, **kwargs)
        image_embedding_adapter: QwenImageEmbeddingAdapterImpl = QwenImageEmbeddingAdapterImpl(config_dict, **kwargs)
        vector_export_adapter: QwenExportAdapterImpl = QwenExportAdapterImpl(config_dict, **kwargs)
        vector_embedding = MultimodalEmbedding(config=config_dict, image_embedding_adapter=image_embedding_adapter)
        vector_export = VectorExport(config=config_dict, export_adapter=vector_export_adapter)
        default_pipeline = StreamProcessPipeline(
            name=Strategy.QWEN_TEXTUAL.name,
            processors=[
                BaseParallel(processors=[BaseSerial(processors=[textual_recognizer, textual_export]),
                                         BaseSerial(processors=[vector_embedding, vector_export]),
                                         BaseSerial(processors=[event_textual_recognizer])])
            ]
        )
        return default_pipeline

    @staticmethod
    def create_textual_pipeline(config_dict: dict, **kwargs):
        #  文本化
        textual_recognizer, textual_export = build_textual_processor(config_dict, **kwargs)
        # todo: 改为parallel
        default_pipeline = StreamProcessPipeline(
            name=Strategy.QWEN_TEXTUAL.name,
            processors=[
                textual_recognizer,
                textual_export
            ]
        )
        return default_pipeline
    
    @staticmethod
    def create_event_only_pipeline(config_dict: dict, **kwargs):
        """
        只包含 event_textual_recognizer，一次吃 30 帧。
        """
        event_textual_recognizer = build_event_textual_processor(config_dict, **kwargs)
        default_pipeline = StreamProcessPipeline(
            name=Strategy.QWEN_TEXTUAL.name,
            processors=[event_textual_recognizer]  
        )
        return default_pipeline