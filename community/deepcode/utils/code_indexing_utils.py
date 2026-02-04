#!/usr/bin/env python
# coding: utf-8
# Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
"""Data structures shared between codebase intelligence components"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

@dataclass

class FileRelationship:
    """Represents a relationship between a repo file and target structure file"""
    repo_file_path: str
    target_file_path: str
    relationship_type: str  # 'direct_match', 'partial_match', 'reference', 'utility'
    confidence_score: float  # 0.0 to 1.0
    helpful_aspects: List[str]
    potential_contributions: List[str]
    usage_suggestions: str

@dataclass
class FileSummary:
    """Summary information for a repository file"""
    file_path: str
    file_type: str
    main_functions: List[str]
    key_concepts: List[str]
    dependencies: List[str]
    summary: str
    lines_of_code: int
    last_modified: str

@dataclass
class RepoIndex:
    """Complete index for a repository"""
    repo_name: str
    total_files: int
    file_summaries: List[FileSummary]
    relationships: List[FileRelationship]
    analysis_metadata: Dict[str, Any]

@dataclass
class IndexerConfig:
    """Data class for indexer configuration"""
    code_base_path: Path
    output_dir: Path
    llm_provider: str = "openai"
    llm_model: str = "gpt-3.5-turbo"
    max_files_per_batch: int = 10
    max_concurrent_files: int = 5
    file_types_to_analyze: List[str] = field(default_factory=lambda: [".py", ".js", ".ts", ".jsx", ".tsx"])
    files_to_exclude: List[str] = field(default_factory=lambda: ["node_modules", ".git", ".venv"])
    include_metadata: bool = True
    generate_summary: bool = True
    generate_statistics: bool = True
    verbose_output: bool = True
    index_filename_pattern: str = "{repo_name}_code_index.json"
    summary_filename: str = "codebase_summary.md"
    stats_filename: str = "codebase_statistics.json"
    initial_plan_path: Optional[Path] = None
    target_structure: Optional[Dict[str, Any]] = None

default_target_structure = '''
project/
├── src/
│   ├── core/
│   │   ├── gcn.py        # GCN encoder
│   │   ├── diffusion.py  # forward/reverse processes
│   │   ├── denoiser.py   # denoising MLP
│   │   └── fusion.py     # fusion combiner
│   ├── models/           # model wrapper classes
│   │   └── recdiff.py
│   ├── utils/
│   │   ├── data.py       # loading & preprocessing
│   │   ├── predictor.py  # scoring functions
│   │   ├── loss.py       # loss functions
│   │   ├── metrics.py    # NDCG, Recall etc.
│   │   └── sched.py      # beta/alpha schedule utils
│   └── configs/
│       └── default.yaml  # hyperparameters, paths
├── tests/
│   ├── test_gcn.py
│   ├── test_diffusion.py
│   ├── test_denoiser.py
│   ├── test_loss.py
│   └── test_pipeline.py
├── docs/
│   ├── architecture.md
│   ├── api_reference.md
│   └── README.md
├── experiments/
│   ├── run_experiment.py
│   └── notebooks/
│       └── analysis.ipynb
├── requirements.txt
└── setup.py
'''

supported_extensions = [
                    ".py",
                    ".js",
                    ".ts",
                    ".java",
                    ".cpp",
                    ".c",
                    ".h",
                    ".hpp",
                    ".cs",
                    ".php",
                    ".rb",
                    ".go",
                    ".rs",
                    ".scala",
                    ".kt",
                    ".swift",
                    ".m",
                    ".mm",
                    ".r",
                    ".matlab",
                    ".sql",
                    ".sh",
                    ".bat",
                    ".ps1",
                    ".yaml",
                    ".yml",
                    ".json",
                    ".xml",
                    ".toml",
                ]

skip_directories = [
                    "__pycache__",
                    "node_modules",
                    "target",
                    "build",
                    "dist",
                    "venv",
                    "env",
                ]
