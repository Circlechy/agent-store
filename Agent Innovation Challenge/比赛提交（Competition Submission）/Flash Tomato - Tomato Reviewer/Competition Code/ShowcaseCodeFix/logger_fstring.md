# Issues in logger_fstring.py

This file demonstrates **f-string usage in logging statements** that pylint will flag.

## Pylint Issues:

1. **F-string in `logger.info`**: Using f-strings in logging calls like `logger.info(f"...")` is inefficient.

2. **F-string in `logger.debug`**: F-strings are evaluated even when the log level is disabled.

3. **F-string in `logger.error`**: F-strings are always evaluated, even if logging is disabled.

4. **F-string in `logger.warning`**: Same issue - f-strings are evaluated regardless of log level.

5. **Pylint messages you'll see**:
   - `logging-fstring-interpolation` for f-strings in logging calls
   - `logging-format-interpolation` suggesting to use % formatting or .format()

## Why this is bad:

- **Performance**: F-strings are evaluated immediately, even when the log level would prevent the message from being logged
- **Inefficiency**: If logging is disabled (e.g., DEBUG level is off), the f-string is still evaluated, wasting CPU cycles
- **Cost**: In production with disabled logging, you're still doing string formatting work for nothing
- **Best practice**: Logging should use lazy evaluation - only format the string if it will actually be logged

## How to fix:

Use C-style formatting with `%` or `.format()` method instead of f-strings:

**Before (bad):**
```python
logger.info(f"Processing user data for user_id: {user_id}, name: {user_name}")
```

**After (good - % formatting):**
```python
logger.info("Processing user data for user_id: %s, name: %s", user_id, user_name)
```

**After (good - .format()):**
```python
logger.info("Processing user data for user_id: {}, name: {}", user_id, user_name)
```

**After (good - % formatting with dict):**
```python
logger.info("Processing user data for user_id: %(user_id)s, name: %(user_name)s", 
            {"user_id": user_id, "user_name": user_name})
```

## Benefits of C-style formatting:

- **Lazy evaluation**: The string is only formatted if the log level allows it
- **Better performance**: No string formatting overhead when logging is disabled
- **Standard practice**: This is the recommended way to use logging in Python
- **Efficient**: The logging module can optimize these calls
