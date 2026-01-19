# SPDX-FileCopyrightText: 2025 MiromindAI
#
# SPDX-License-Identifier: Apache-2.0
from .models import ModelManager

model_manager = ModelManager()

__all__ = [
    'model_manager'
]