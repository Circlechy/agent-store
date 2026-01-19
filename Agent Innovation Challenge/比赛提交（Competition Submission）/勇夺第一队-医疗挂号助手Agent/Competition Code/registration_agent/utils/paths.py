from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def assistant_dir() -> Path:
    return project_root() / "assistant_agent"


def doctor_data_dir() -> Path:
    return project_root() / "doctor_data"
