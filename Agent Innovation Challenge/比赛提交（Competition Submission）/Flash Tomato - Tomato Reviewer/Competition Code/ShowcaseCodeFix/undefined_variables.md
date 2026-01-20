# Issues in undefined_variables.py

This file demonstrates **undefined variables** that pylint will flag.

## Pylint Issues:

1. **Undefined variable `undefined_result`**: In the `process_data` function, the variable `undefined_result` is referenced but never defined.

2. **Undefined variable `missing_value`**: In the `calculate_total` function, the variable `missing_value` is referenced but never defined.

3. **Undefined attribute `price`**: In the `calculate_total` function, the code tries to access `item.price` but `item` is just an integer from the list, not an object with a `price` attribute.

4. **Pylint messages you'll see**:
   - `undefined-variable` for undefined variables
   - `no-member` for undefined attributes

## How to fix:

- Define all variables before using them
- Ensure objects have the attributes you're trying to access
- Use proper data structures (e.g., dictionaries or objects) if you need to access attributes
