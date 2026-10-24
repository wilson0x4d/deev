# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

import hanaro

T = TypeVar('T')


def __log_task_exception(task: asyncio.Task[Any]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        hanaro.get_logger().error(f'async_run scheduled task failed: {exc}', exc_info=exc)


def async_run(coro: Coroutine[Any, Any, T]) -> T | None:
    """
    Run a coroutine to completion from a synchronous context.

    If the current thread has a running event loop, the coroutine is scheduled
    on it as a task and ``None`` is returned immediately (the task runs
    concurrently; any exception it raises is logged via a done-callback).
    Otherwise, the coroutine is run via :func:`asyncio.run`, which blocks the
    current thread until completion, returns the coroutine's result, and
    propagates any exception it raises.

    :param coro: The coroutine to run.
    :return: The coroutine's result, or ``None`` when scheduled on a running loop.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        task = loop.create_task(coro)
        task.add_done_callback(__log_task_exception)
        return None
    return asyncio.run(coro)


__all__ = ['async_run']
