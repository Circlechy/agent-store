from pathlib import Path

from openjiuwen.core.common.logging import logger

logger.config["output"] = ["file"]
logger.reconfigure(logger.config)

__version__ = (Path(__file__).parent / "version.txt").read_text().strip()
