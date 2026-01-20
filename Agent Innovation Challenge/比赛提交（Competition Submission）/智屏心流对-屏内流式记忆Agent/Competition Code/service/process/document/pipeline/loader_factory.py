from doc_process.processors.base.adapter.layout_recog_adapter import LayoutRecogAdapter
from doc_process.processors.document.loaders.doc_directory_loader import DocumentDirectoryLoader
from doc_process.processors.document.parsers.pdf_parser import PDFParser
from doc_process.utils import logging
from service.process.document.adapter_impl.layout_recog_adapter_impl import LayoutRecogAdapterImpl

logger = logging.get_logger()


class LoaderFactory:
    """LoaderFactory"""

    @staticmethod
    def create_directory_loader(config_dict: dict):
        layout_recog_adapter_impl: LayoutRecogAdapter = LayoutRecogAdapterImpl(config=config_dict)

        pdf_parser = PDFParser(
            config=config_dict, layout_recognizer=layout_recog_adapter_impl
        )

        directory_loader = DocumentDirectoryLoader(
            config=config_dict,
            file_extractor={".pdf": pdf_parser}
        )
        return directory_loader
