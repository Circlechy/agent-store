# Issues in complex_comprehension.py

This file demonstrates **overly complex comprehensions** that pylint will flag.

## Pylint Issues:

1. **Too complex list comprehension in `process_matrix`**: The comprehension has multiple nested conditions and operations, making it hard to read.

2. **Too complex dict comprehension in `filter_and_transform`**: The comprehension has nested loops and multiple conditions.

3. **Triple-nested list comprehension in `nested_comprehension`**: Three levels of nesting make it extremely difficult to understand.

4. **Extremely complex dict comprehension in `complex_dict_comprehension`**: Multiple nested loops, conditions, and operations in a single comprehension.

5. **Pylint messages you'll see**:
   - `too-complex` for comprehensions that exceed complexity thresholds
   - `simplifiable-comprehension` for comprehensions that can be simplified
   - `consider-using-generator` for comprehensions that could be generators

## Why this is bad:

- **Readability**: Complex comprehensions are hard to read and understand
- **Maintainability**: Difficult to debug and modify
- **Performance**: May not be more efficient than explicit loops
- **Error-prone**: Easy to make mistakes with nested comprehensions
- **Testing**: Hard to test individual parts

## How to fix:

- Break complex comprehensions into multiple lines
- Use explicit for loops for complex logic
- Extract helper functions for complex operations
- Use intermediate variables to improve readability
- Consider using generator expressions for large datasets
- Limit nesting to 2 levels maximum
- Separate filtering from transformation
