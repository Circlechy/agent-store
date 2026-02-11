__all__ = ["__version__", "PYLINT_FALLBACK", "MYPY_FALLBACK", "DEBUG_MODE"]

import os
import subprocess
from pathlib import Path

from openjiuwen.core.common.logging import llm_logger, logger

for lg in [logger, llm_logger]:
    lg.config["output"] = ["file"]
    lg.reconfigure(logger.config)

__version__ = (Path(__file__).parent / "version.txt").read_text().strip()
PYLINT_FALLBACK = (Path(__file__).parent / ".pylintrc").absolute()
MYPY_FALLBACK = (Path(__file__).parent / ".mypy.ini").absolute()
DEBUG_MODE = False
os.environ["GRPC_VERBOSITY"] = "ERROR"

# Run mypy --install-types at startup to install type stubs
try:
    subprocess.run(
        ["mypy", "--install-types", "--non-interactive"],
        capture_output=True,
        timeout=30,
        check=False,
    )
except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
    # Silently ignore if mypy is not installed or if the command fails
    pass
