# Issues in line_too_long.py

This file demonstrates **lines that are too long** that pylint will flag.

## Pylint Issues:

1. **Line too long in `process_user_data`**: The function definition line exceeds the recommended 79 or 100 character limit.

2. **Line too long in function body**: The dictionary creation line is too long.

3. **Line too long in `calculate_complex_formula`**: The function definition and the calculation line are too long.

4. **Line too long in `main`**: Function call lines exceed the character limit.

5. **Pylint messages you'll see**:
   - `line-too-long` for lines exceeding the configured limit (default 100, PEP 8 recommends 79)

## How to fix:

- Break long lines into multiple lines
- Use parentheses for implicit line continuation
- Break function arguments across multiple lines
- Use backslashes for explicit line continuation (less preferred)
- Follow PEP 8: limit lines to 79 characters (or 99 for some projects)
