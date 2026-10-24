# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

import asyncio
import threading
from typing import Callable

from punit import fact, raises, trait

from deev.common import async_run
from deev.entities import (
    ON_CREATE_TABLE,
    entity,
    field,
    get_entity_spec,
    get_on_create_table_hook,
    invoke_on_create_table,
    invoke_on_create_table_async,
)


@fact
@trait('unit')
def on_create_table_name_constant() -> None:
    assert ON_CREATE_TABLE == 'on_create_table', f"(expected='on_create_table', actual={ON_CREATE_TABLE})"


@fact
@trait('unit')
def hook_detected_on_entity_class() -> None:
    @entity
    class HookedEntity:
        id: int = field(primary_key=True)

        @staticmethod
        def on_create_table(table_adapter) -> None:
            pass

    hook = get_on_create_table_hook(HookedEntity)
    assert hook is not None, 'hook should be detected on the entity class'
    assert hook.__name__ == 'on_create_table', f"(expected='on_create_table', actual={hook.__name__})"


@fact
@trait('unit')
def no_hook_returns_none() -> None:
    @entity
    class PlainEntity:
        id: int = field(primary_key=True)

    assert get_on_create_table_hook(PlainEntity) is None, f"(expected=None, actual={get_on_create_table_hook(PlainEntity)})"


@fact
@trait('unit')
def non_callable_attribute_ignored() -> None:
    @entity
    class WeirdEntity:
        id: int = field(primary_key=True)
        on_create_table = 'not-callable'  # type: ignore[assignment]

    assert get_on_create_table_hook(WeirdEntity) is None, f"(expected=None, actual={get_on_create_table_hook(WeirdEntity)})"


@fact
@trait('unit')
def hook_inherited_from_base_class() -> None:
    class Base:
        @staticmethod
        def on_create_table(table_adapter) -> None:
            pass

    @entity
    class ChildEntity(Base):
        id: int = field(primary_key=True)

    assert get_on_create_table_hook(ChildEntity) is not None, 'inherited hook should be detected via the MRO'


@fact
@trait('unit')
def annotated_hook_excluded_from_fields() -> None:
    @entity
    class AnnotatedEntity:
        id: int = field(primary_key=True)
        on_create_table: Callable

        @staticmethod  # type: ignore[no-redef]
        def on_create_table(table_adapter) -> None:
            pass

    spec = get_entity_spec(AnnotatedEntity)
    assert 'on_create_table' not in spec.fields, f"(expected=on_create_table not in fields, actual={tuple(spec.fields)})"
    assert 'on_create_table' not in spec.attrs, f"(expected=on_create_table not in attrs, actual={tuple(spec.attrs)})"


@fact
@trait('unit')
def sync_hook_invoked_with_adapter() -> None:
    calls = []

    @entity
    class HookedEntity:
        id: int = field(primary_key=True)

        @staticmethod
        def on_create_table(table_adapter) -> None:
            calls.append(table_adapter)

    sentinel = object()
    invoke_on_create_table(HookedEntity, sentinel)
    assert len(calls) == 1, f"(expected=1, actual={len(calls)})"
    assert calls[0] is sentinel, 'hook must receive the table adapter as its sole argument'


@fact
@trait('unit')
def no_hook_is_noop() -> None:
    @entity
    class PlainEntity:
        id: int = field(primary_key=True)

    invoke_on_create_table(PlainEntity, object())
    assert True, 'invoke_on_create_table must be a no-op when no hook is defined'


@fact
@trait('unit')
def async_hook_sync_path_without_running_loop() -> None:
    calls = []

    @entity
    class HookedEntity:
        id: int = field(primary_key=True)

        @staticmethod
        async def on_create_table(table_adapter) -> None:
            calls.append(table_adapter)

    sentinel = object()

    # a worker thread has no running event loop, so the coroutine is run to
    # completion via asyncio.run (blocking the thread)
    def run_in_thread() -> None:
        invoke_on_create_table(HookedEntity, sentinel)

    thread = threading.Thread(target=run_in_thread)
    thread.start()
    thread.join()
    assert calls == [sentinel], f"(expected=[sentinel], actual={calls})"


@fact
@trait('unit')
async def async_hook_sync_path_with_running_loop_schedules_task() -> None:
    calls = []

    @entity
    class HookedEntity:
        id: int = field(primary_key=True)

        @staticmethod
        async def on_create_table(table_adapter) -> None:
            calls.append(table_adapter)

    sentinel = object()
    invoke_on_create_table(HookedEntity, sentinel)
    # the coroutine is scheduled as a task on the running loop
    await asyncio.sleep(0.05)
    assert calls == [sentinel], f"(expected=[sentinel], actual={calls})"


@fact
@trait('unit')
async def async_hook_awaited_on_async_path() -> None:
    calls = []

    @entity
    class HookedEntity:
        id: int = field(primary_key=True)

        @staticmethod
        async def on_create_table(table_adapter) -> None:
            calls.append(table_adapter)
            await asyncio.sleep(0.01)

    sentinel = object()
    await invoke_on_create_table_async(HookedEntity, sentinel)
    assert calls == [sentinel], f"(expected=[sentinel], actual={calls})"


@fact
@trait('unit')
async def sync_hook_works_on_async_path() -> None:
    calls = []

    @entity
    class HookedEntity:
        id: int = field(primary_key=True)

        @staticmethod
        def on_create_table(table_adapter) -> None:
            calls.append(table_adapter)

    sentinel = object()
    await invoke_on_create_table_async(HookedEntity, sentinel)
    assert calls == [sentinel], f"(expected=[sentinel], actual={calls})"


@fact
@trait('unit')
def async_run_without_loop_returns_value() -> None:
    async def coro() -> int:
        return 42

    # a worker thread has no running event loop, so the coroutine is run to
    # completion via asyncio.run (blocking the thread)
    results: list[int | None] = []
    thread = threading.Thread(target=lambda: results.append(async_run(coro())))
    thread.start()
    thread.join()
    assert results == [42], f"(expected=[42], actual={results})"


@fact
@trait('unit')
def async_run_without_loop_propagates_exception() -> None:
    async def coro() -> None:
        raise ValueError('boom')

    # a worker thread has no running event loop, so the coroutine is run to
    # completion via asyncio.run (blocking the thread)
    errors: list[Exception] = []

    def run_in_thread() -> None:
        try:
            async_run(coro())
        except ValueError as e:
            errors.append(e)

    thread = threading.Thread(target=run_in_thread)
    thread.start()
    thread.join()
    assert len(errors) == 1 and isinstance(errors[0], ValueError), 'async_run must propagate exceptions from the coroutine'


@fact
@trait('unit')
async def async_run_with_running_loop_schedules_task() -> None:
    state = {'ran': False}

    async def coro() -> None:
        state['ran'] = True

    result = async_run(coro())
    assert result is None, f"(expected=None when scheduled on a running loop, actual={result})"
    await asyncio.sleep(0.05)
    assert state['ran'] is True, 'scheduled task should have completed'
