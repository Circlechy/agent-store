# Issues in too_many_arguments.py

This file demonstrates **too many arguments** in function definitions that pylint will flag.

## Pylint Issues:

1. **Too many arguments in `create_user_profile`**: The function has 15 parameters, which exceeds pylint's default limit (usually 5).

2. **Too many arguments in `process_order`**: The function has 13 parameters, which also exceeds the limit.

3. **Pylint messages you'll see**:
   - `too-many-arguments` for functions with too many parameters

## How to fix:

- Use a dictionary or dataclass to group related parameters
- Use keyword-only arguments
- Refactor into smaller functions
- Use configuration objects or data classes to pass multiple related values
