# Issues in missing_docstrings.py

This file demonstrates **missing docstrings** that pylint will flag.

## Pylint Issues:

1. **Missing module docstring**: The module doesn't have a docstring at the top.

2. **Missing class docstring**: The `Calculator` class doesn't have a docstring.

3. **Missing method docstrings**: All methods in the `Calculator` class lack docstrings.

4. **Missing function docstrings**: Functions like `process_items` and `calculate_average` don't have docstrings.

5. **Pylint messages you'll see**:
   - `missing-module-docstring`
   - `missing-class-docstring`
   - `missing-function-docstring`

## How to fix:

- Add docstrings to all modules, classes, and public functions
- Follow Google, NumPy, or Sphinx docstring style
- Document parameters, return values, and exceptions
- Use triple-quoted strings ("""...""") for docstrings
