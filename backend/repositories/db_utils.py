import time
import asyncio
from typing import Callable, Any


def execute_with_retry(action, retries: int = 3, backoff: float = 0.2):
    """Execute a callable with basic retry and linear backoff.

    Keep this simple: only use for short DB operations.
    """
    last_exc = None
    for attempt in range(retries):
        try:
            return action()
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    raise last_exc


async def run_in_executor(action: Callable[[], Any]):
    """Run a blocking callable in the default thread executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, action)
