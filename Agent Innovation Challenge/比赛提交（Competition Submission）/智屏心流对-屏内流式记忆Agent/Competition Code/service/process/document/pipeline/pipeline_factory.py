from doc_process.config_repository.document.mapping import BaseMappingField, MappingField
from doc_process.pipeline_manage.pipeline import DocumentProcessPipeline
from doc_process.processors.base.adapter.layout_recog_adapter import LayoutRecogAdapter
from doc_process.processors.document.bm25.doc_bm25 import DocumentBm25
from doc_process.processors.document.delete.doc_delete_combine import DocumentDeleteCombine
from doc_process.processors.document.delete.doc_delete_es import DocumentDeleteEs
from doc_process.processors.document.delete.doc_delete_vs import DocumentDeleteVs
from doc_process.processors.document.embedding.doc_embedding import DocumentEmbedding
from doc_process.processors.document.export.doc_export_es import DocumentExportEs
from doc_process.processors.document.export.doc_export_vs import DocumentExportVs
from doc_process.processors.document.extractors.doc_structure_summary_generator import DocumentStructureSummaryExtractor
from doc_process.processors.document.parallel.doc_parallel import DocumentParallel
from doc_process.processors.document.parsers.pdf_parser import PDFParser
from doc_process.processors.document.splitters.doc_segmentor_based_splitter import ParaSplitter
from service.process.document.adapter_impl.embedding_adapter_impl import TextEmbeddingAdapterImpl
from service.process.document.adapter_impl.es_adapter_impl import EsAdapterImpl
from service.process.document.adapter_impl.layout_recog_adapter_impl import LayoutRecogAdapterImpl
from service.process.document.adapter_impl.summary_adapter_impl import AutoLLMForSummarization
from service.process.document.adapter_impl.vs_adapter_impl import VsAdapterImpl


class PipelineFactory:
    """PipelineFactory"""

    @staticmethod
    def create_default_pipeline(config_dict: dict):
        layout_recog_adapter_impl: LayoutRecogAdapter = LayoutRecogAdapterImpl(config=config_dict)
        pdf_parser = PDFParser(
            config=config_dict, layout_recognizer=layout_recog_adapter_impl
        )
        summary_adapter = AutoLLMForSummarization.from_pretrained(config_dict)
        embedding_adapter: TextEmbeddingAdapterImpl = TextEmbeddingAdapterImpl(config_dict)
        index_mapping: BaseMappingField = MappingField(config=config_dict)
        es_adapter = EsAdapterImpl(config_dict, index_mapping)
        vs_adapter = VsAdapterImpl(config_dict, index_mapping)

        default_pipeline = DocumentProcessPipeline(
            name="default",
            processors=[
                ParaSplitter(config=config_dict),
                DocumentStructureSummaryExtractor(config=config_dict,
                                                  adapter=summary_adapter),
                DocumentParallel(bm25=DocumentBm25(config=config_dict, mapping=index_mapping, bm25_adapter=es_adapter),
                                 embedding=DocumentEmbedding(config=config_dict, mapping=index_mapping,
                                                     embedding_adapter=embedding_adapter)),
                DocumentExportEs(config=config_dict, es_adapter=es_adapter, mapping=index_mapping),
                DocumentExportVs(config=config_dict, vs_adapter=vs_adapter, mapping=index_mapping)
            ]
        )
        return default_pipeline

    @staticmethod
    def create_rag_delete_pipeline(config_dict: dict):
        layout_recog_adapter_impl: LayoutRecogAdapter = LayoutRecogAdapterImpl(config=config_dict)
        pdf_parser = PDFParser(
            config=config_dict, layout_recognizer=layout_recog_adapter_impl
        )
        summary_adapter = AutoLLMForSummarization.from_pretrained(config_dict)
        embedding_adapter: TextEmbeddingAdapterImpl = TextEmbeddingAdapterImpl(config_dict)
        index_mapping: BaseMappingField = MappingField(config=config_dict)
        es_adapter = EsAdapterImpl(config_dict, index_mapping)
        vs_adapter = VsAdapterImpl(config_dict, index_mapping)

        rag_delete_pipeline = DocumentProcessPipeline(name="delete",
                                                      processors=[
                                                          DocumentDeleteCombine(deletes=[DocumentDeleteVs(vs_adapter=vs_adapter),
                                                                                         DocumentDeleteEs(es_adapter=es_adapter)])
                                                      ])
        return rag_delete_pipeline
