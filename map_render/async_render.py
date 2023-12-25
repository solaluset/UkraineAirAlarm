import asyncio
from concurrent.futures import ProcessPoolExecutor


def _render():
    from .map_render import get_img

    return get_img()


_executor = ProcessPoolExecutor(1)


async def render():
    return await asyncio.get_running_loop().run_in_executor(_executor, _render)
