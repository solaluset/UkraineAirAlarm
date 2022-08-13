import asyncio
from concurrent.futures import ProcessPoolExecutor


def _render(wait_for_new):
    from .map_render import get_img

    return get_img(wait_for_new)


_executor = ProcessPoolExecutor(1)


async def render(wait_for_new=False):
    return await asyncio.get_running_loop().run_in_executor(
        _executor, _render, wait_for_new
    )
