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
                        f"Errored when trying to run '{func.__name__}', attempt {attempt} of {times}"
                    )
                    attempt += 1
            return func(*args, **kwargs)

        return newfn

    return decorator


def percentile(values, p):
    if not values:
        return 0

    values = sorted(values)
    index = int(len(values) * (p / 100))

    # prevent out-of-range index
    index = min(index, len(values) - 1)

    return values[index]
