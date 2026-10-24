# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

import inspect
from typing import Any, Callable

from ..common.async_run import async_run

ON_CREATE_TABLE = 'on_create_table'


def get_on_create_table_hook(entity_type: type) -> Callable[..., Any] | None:
    """
    Retrieve the ``on_create_table`` hook for *entity_type*, or ``None`` if not defined.

    The hook is looked up by name on the class (inherited definitions are found
    via the MRO) and must be callable; a non-callable attribute of the same name
    is ignored.

    :param entity_type: The entity class.
    :return: The hook callable, or ``None``.
    """
    hook = getattr(entity_type, ON_CREATE_TABLE, None)
    return hook if callable(hook) else None


def invoke_on_create_table(entity_type: type, table_adapter: Any) -> None:
    """
    Invoke the ``on_create_table`` hook for *entity_type*, if defined, from a synchronous context.

    The hook is called with *table_adapter* as its sole argument. If the hook is a
    coroutine function, the resulting coroutine is executed via
    :func:`deev.common.async_run` (scheduled on the current thread's running event
    loop, or run to completion in a new loop).

    :param entity_type: The entity class.
    :param table_adapter: The table adapter whose ``create_table`` created the table.
    """
    hook = get_on_create_table_hook(entity_type)
    if hook is None:
        return
    result = hook(table_adapter)
    if inspect.iscoroutine(result):
        async_run(result)


async def invoke_on_create_table_async(entity_type: type, table_adapter: Any) -> None:
    """
    Invoke the ``on_create_table`` hook for *entity_type*, if defined, from an asynchronous context.

    The hook is called with *table_adapter* as its sole argument. If the hook is a
    coroutine function, the resulting coroutine is awaited.

    :param entity_type: The entity class.
    :param table_adapter: The table adapter whose ``create_table`` created the table.
    """
    hook = get_on_create_table_hook(entity_type)
    if hook is None:
        return
    result = hook(table_adapter)
    if inspect.iscoroutine(result):
        await result


__all__ = [
    'ON_CREATE_TABLE',
    'get_on_create_table_hook',
    'invoke_on_create_table',
    'invoke_on_create_table_async',
]
