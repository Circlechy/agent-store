# -*- coding: utf-8 -*-
"""工作流定义"""

from .record_input_workflow import create_record_input_workflow
from .report_generation_workflow import create_report_generation_workflow

__all__ = [
    'create_record_input_workflow',
    'create_report_generation_workflow',
]
