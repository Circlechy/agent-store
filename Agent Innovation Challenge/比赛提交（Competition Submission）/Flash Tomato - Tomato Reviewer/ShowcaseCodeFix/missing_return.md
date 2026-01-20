# Issues in missing_return.py

This file demonstrates **missing return statements** that pylint will flag.

## Pylint Issues:

1. **Missing return in `calculate_sum`**: The function calculates `result` but doesn't return it, so it returns `None` implicitly.

2. **Missing return in `get_user_name`**: The `else` branch doesn't return anything, so the function may return `None`.

3. **Missing return in `process_data`**: If `data` is falsy, the function doesn't return anything explicitly.

4. **Pylint messages you'll see**:
   - `missing-return` or `inconsistent-return-statements` for functions that don't return in all code paths
   - `no-else-return` suggesting to remove unnecessary else after return

## How to fix:

- Ensure all code paths in a function return a value (if the function is supposed to return something)
- Add explicit return statements
- Use early returns to simplify control flow
- Consider returning a default value instead of `None` if appropriate
