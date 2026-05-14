# SPDX-FileCopyrightText: © 2023 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations
from deev.common import (
    DbConnection,
    DbContext,
    DbCursor,
    DbTransactionContext,
    DbTypeMapper
)
from deev.mysql import MysqlTransactionContext, MysqlTypeMapper
import inspect
from mysql.connector.abstracts import (
    MySQLConnectionAbstract,
    MySQLCursorAbstract
)
from punit import theory, inlinedata
from typing import Any, get_type_hints


def __protocol_mismatch_report(proto: type, candidate: type) -> str:
    is_mismatch = False
    report = []
    # ----- 1. What the Protocol requires ---------------------------------
    required: dict[str, Any] = {}
    for name, value in inspect.getmembers(proto):
        if name.startswith('_'):
            continue
        # Methods / callables
        if inspect.isfunction(value) or inspect.ismethoddescriptor(value):
            required[name] = ('callable', inspect.signature(value))
        # Properties (including @property)
        elif isinstance(value, property):
            required[name] = ('property', get_type_hints(value.fget).get('return', Any))
        # Class variables / attributes
        else:
            required[name] = ('attr', get_type_hints(proto).get(name, Any))

    # ----- 2. What the candidate actually has ----------------------------
    provided: dict[str, Any] = {}
    for name in required.keys():
        if not hasattr(candidate, name):
            continue
        attr = getattr(candidate, name)
        if callable(attr):
            provided[name] = ('callable', inspect.signature(attr))
        elif isinstance(attr, property):
            provided[name] = ('property', get_type_hints(attr.fget).get('return', Any))
        else:
            provided[name] = ('attr', type(attr))

    # ----- 3. Report mismatches -------------------------------------------
    missing = [n for n in required if n not in provided]
    if missing:
        is_mismatch = True
        report.append('Missing members required by the Protocol:')
        for n in missing:
            report.append(f'  - {n}')
    else:
        report.append('All required members are present.')

    # Signature / type mismatches
    for name, (kind, req_sig) in required.items():
        if name not in provided:
            continue
        prov_kind, prov_sig = provided[name]
        if kind != prov_kind:
            report.append(f'Kind mismatch for {name}: protocol expects {kind}, class has {prov_kind}')
            is_mismatch = True
            continue
        if kind == 'callable':
            # Compare params (ignoring *self/*cls for methods)
            req_params = list(req_sig.params.values())
            prov_params = list(prov_sig.params.values())
            # drop the first param if it looks like self/cls
            if req_params and req_params[0].name in {'self', 'cls'}:
                req_params = req_params[1:]
            if prov_params and prov_params[0].name in {'self', 'cls'}:
                prov_params = prov_params[1:]

            if len(req_params) != len(prov_params):
                report.append(f'Signature mismatch for {name}: different number of params')
                is_mismatch = True
                continue
            for rp, pp in zip(req_params, prov_params):
                if rp.kind != pp.kind:
                    report.append(f'  Parameter kind mismatch in {name}: {rp} vs {pp}')
                    is_mismatch = True
        elif kind == 'property':
            # Simple type-annotation check
            if req_sig != prov_sig:
                report.append(f'Type mismatch for property {name}: protocol says {req_sig}, class has {prov_sig}')
                is_mismatch = True
    result = '\r\n'.join(report)
    if is_mismatch:
        raise AssertionError(result)
    return result


@theory
@inlinedata(MySQLConnectionAbstract, DbConnection)
@inlinedata(MySQLConnectionAbstract, DbContext)
@inlinedata(MySQLCursorAbstract, DbCursor)
@inlinedata(MysqlTransactionContext, DbConnection)
@inlinedata(MysqlTransactionContext, DbTransactionContext)
@inlinedata(MysqlTypeMapper, DbTypeMapper)
def protocols_runtime_test(candidate: type, proto: type) -> None:
    """Assert verious types can be runtime-checked for their equivalent Protocol(s)"""
    if not issubclass(candidate, proto):
        print(__protocol_mismatch_report(proto, candidate))
