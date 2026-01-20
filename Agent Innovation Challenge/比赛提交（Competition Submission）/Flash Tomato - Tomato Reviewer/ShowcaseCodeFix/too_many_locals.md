# Issues in too_many_locals.py

This file demonstrates **too many local variables** that pylint will flag.

## Pylint Issues:

1. **Too many local variables in `complex_calculation`**: The function has 20 local variables (step1 through step20), which exceeds pylint's default limit (usually 15).

2. **Too many local variables in `process_user_info`**: The function has 13 local variables, which may also exceed the limit.

3. **Pylint messages you'll see**:
   - `too-many-locals` for functions with too many local variables

## How to fix:

- Refactor into smaller functions
- Group related variables into data structures (dictionaries, dataclasses)
- Use more descriptive variable names and combine operations
- Extract complex logic into separate helper functions
- Consider using a class if the function is managing too much state
