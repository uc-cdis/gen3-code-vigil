import time


def retry(times, delay, exceptions):
    """
    Decorator that retries the wrapped function/method `times` times if the exceptions
    listed in ``exceptions`` are thrown waiting for `delay` seconds between retries
    """

    def decorator(func):
        def newfn(*args, **kwargs):
            attempt = 1
            while attempt <= times:
                time.sleep(delay)
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    print(
                        f"Errored when trying to run {func}, attempt {attempt} of {times}"
                    )
                    attempt += 1
            return func(*args, **kwargs)

        return newfn

    return decorator
