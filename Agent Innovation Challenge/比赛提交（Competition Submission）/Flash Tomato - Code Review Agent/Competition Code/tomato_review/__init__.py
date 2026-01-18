from openjiuwen.core.common.logging import logger

logger.config["output"] = ["file"]
logger.reconfigure(logger.config)
