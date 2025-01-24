import asyncio
import functools

# Wraps sync python function into awaitable. Only useful if implementation releases GIL
def blocking_to_async(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(None, functools.partial(f, *args, **kwargs))

    return inner