from __future__ import annotations

import sys
from pathlib import Path

import uvicorn

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.config.settings import settings


def main() -> None:
    uvicorn.run(
        "backend.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    main()
