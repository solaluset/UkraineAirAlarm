import asyncio
from concurrent.futures import ProcessPoolExecutor


def _render():
    from .map_render import get_img

    return get_img()


_executor = None


async def render():
    global _executor
    if not _executor:
        _executor = ProcessPoolExecutor(1)
    return await asyncio.get_running_loop().run_in_executor(_executor, _render)
