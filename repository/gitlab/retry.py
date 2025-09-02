import time
import functools

def retry(max_retries=3, retry_delay=1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            errors = []

            while attempts < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    func_name = func.__qualname__
                    print(f"Error in {func_name}: {e!r}, "
                          f"Retrying ({attempts + 1}/{max_retries})...")
                    errors.append(repr(e))
                    attempts += 1
                    time.sleep(min(retry_delay, 10))

            raise Exception(
                f"Max retries ({max_retries}) reached for {func_name}. "
                f"Unable to complete the operation. "
                f"Original errors: {errors}")

        return wrapper
    return decorator
