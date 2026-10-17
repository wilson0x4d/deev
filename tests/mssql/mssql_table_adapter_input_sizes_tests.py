# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from deev import entity, field
from deev.mssql.mssql_table_adapter import MSSQLTableAdapter
from mssql_python.constants import ConstantsDDBC as C
from punit import fact, trait
from punit.mocks import Mock


@entity
class AdapterInputSizesEntity:
    skey: str = field(primary_key=True, max=20)


def __adapter_and_mock_cursor(use_setinputsizes: bool | None = None) -> tuple[MSSQLTableAdapter[AdapterInputSizesEntity], Mock]:
    mock_cursor = Mock()
    mock_cursor.fetchone.returns(None)
    mock_context = Mock()
    mock_context.cursor.returns(mock_cursor)
    if use_setinputsizes is None:
        adapter = MSSQLTableAdapter[AdapterInputSizesEntity](mock_context)  # type: ignore[arg-type]
    else:
        adapter = MSSQLTableAdapter[AdapterInputSizesEntity](mock_context, use_setinputsizes=use_setinputsizes)  # type: ignore[arg-type]
    return adapter, mock_cursor


@fact
@trait('mssql')
@trait('unit')
def internal_input_sizes_disabled_when_unspecified() -> None:
    adapter, mock_cursor = __adapter_and_mock_cursor()
    adapter.exists(skey='abc')
    assert mock_cursor.setinputsizes.called is False


@fact
@trait('mssql')
@trait('unit')
def internal_input_sizes_disabled_when_false() -> None:
    adapter, mock_cursor = __adapter_and_mock_cursor(use_setinputsizes=False)
    adapter.exists(skey='abc')
    assert mock_cursor.setinputsizes.called is False


@fact
@trait('mssql')
@trait('unit')
def internal_input_sizes_enabled_when_true() -> None:
    adapter, mock_cursor = __adapter_and_mock_cursor(use_setinputsizes=True)
    adapter.exists(skey='abc')
    # skey is NVARCHAR(20) per the field spec; the 3-char value does not shrink it
    assert mock_cursor.setinputsizes.called_with([(C.SQL_WVARCHAR.value, 20, 0)])


@fact
@trait('mssql')
@trait('unit')
def internal_input_sizes_apply_and_execute_in_single_step() -> None:
    adapter, mock_cursor = __adapter_and_mock_cursor(use_setinputsizes=True)
    adapter.exists(skey='abc')
    # the declaration is applied to the same cursor that executes the statement
    assert mock_cursor.setinputsizes.called
    assert mock_cursor.execute.called
    assert mock_cursor.setinputsizes.call_count == 1
