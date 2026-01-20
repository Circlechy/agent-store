# Issues in bad_naming.py

This file demonstrates **bad naming conventions** that pylint will flag.

## Pylint Issues:

1. **Function name `calc`**: Too short, doesn't follow naming convention (should be descriptive like `calculate`).

2. **Function name `ProcessData`**: Uses PascalCase instead of snake_case (should be `process_data`).

3. **Class name `myClass`**: Should use PascalCase properly (should be `MyClass`), and "my" is not descriptive.

4. **Variable names `a`, `b`, `c`**: Too short and not descriptive.

5. **Pylint messages you'll see**:
   - `invalid-name` for names that don't follow PEP 8 conventions
   - `too-short-variable-name` for single-letter variables
   - `function-redefined` if functions are redefined

## How to fix:

- Use descriptive names following PEP 8:
  - Functions and variables: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
- Avoid single-letter variable names except for loop counters
- Use meaningful names that describe the purpose
