import time

from doc_process.utils import logging

# from search.flash_vstream1.mm_utils import get_model_name_from_path
# from search.flash_vstream1.model.builder import load_pretrained_model

logger = logging.get_logger()


def listen_and_push(proactive_push_queue):
    while True:
        time.sleep(5)
        if not proactive_push_queue.empty():
            text, segments_file = proactive_push_queue.get()
            logger.info("listen_and_push:{}".format(text))
            return text, segments_file


class QwenPushService:
    pass
