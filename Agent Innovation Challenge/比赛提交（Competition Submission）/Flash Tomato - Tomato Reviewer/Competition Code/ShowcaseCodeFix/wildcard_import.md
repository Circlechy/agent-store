# Issues in wildcard_import.py

This file demonstrates **wildcard imports** (`import *`) that pylint will flag.

## Pylint Issues:

1. **Wildcard import from `math`**: `from math import *` imports all names from the math module, which can cause namespace pollution.

2. **Wildcard import from `os`**: `from os import *` imports all names from the os module.

3. **Wildcard import from `sys`**: `from sys import *` imports all names from the sys module.

4. **Wildcard import from `typing`**: `from typing import *` imports all names from the typing module.

5. **Pylint messages you'll see**:
   - `wildcard-import` for each wildcard import statement
   - `undefined-all-variable` if `__all__` is not defined in the imported module

## Why this is bad:

- **Namespace pollution**: Imports all names, making it unclear which names come from which module
- **Name conflicts**: Can overwrite existing names in your namespace
- **Hard to track**: Difficult to know which functions/classes are being used
- **Poor readability**: Readers can't tell where names come from
- **IDE support**: Makes autocomplete and static analysis harder

## How to fix:

- Use explicit imports: `from math import pi, sqrt, sin, cos`
- Import the module: `import math` and use `math.pi`
- Only import what you need
- Use `__all__` in your own modules if you want to control what gets exported
