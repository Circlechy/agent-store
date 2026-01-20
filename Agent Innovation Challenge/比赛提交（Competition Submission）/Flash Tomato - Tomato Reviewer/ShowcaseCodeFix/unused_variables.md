# Issues in unused_variables.py

This file demonstrates **unused variables** that pylint will flag.

## Pylint Issues:

1. **Unused variable `unused_var`**: Defined but never used in `process_data`.

2. **Unused variable `unused_count`**: Defined but never used in `calculate_stats`.

3. **Unused variable `temp_result`**: Could be simplified - the intermediate variable is only used once.

4. **Pylint messages you'll see**:
   - `unused-variable` for variables that are assigned but never used
   - `unused-argument` for function parameters that aren't used

## How to fix:

- Remove unused variables
- If a variable is intentionally unused (e.g., in exception handling), prefix it with `_` (e.g., `_unused_var`)
- Simplify code by removing unnecessary intermediate variables
- Use variables only when they improve readability
