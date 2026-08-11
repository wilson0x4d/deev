# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations
from deev.common import (
    DbConnection,
    DbContext,
    DbCursor,
    DbTransactionContext,
    DbTypeMapper
)
from deev.clickhouse import (
    ClickHouseProxyConnection,
    ClickHouseProxyCursor,
    ClickHouseTransactionContext,
    ClickHouseTypeMapper
)
import inspect
from clickhouse_connect.driver.client import Client
from clickhouse_connect.driver.httpclient import HttpClient
from clickhouse_connect.dbapi.connection import Connection as ClickHouseDBAPIConnection
from punit import theory, inlinedata
from typing import Any, get_type_hints


def __protocol_mismatch_report(proto: type, candidate: type) -> str:
    is_mismatch = False
    report = []
    required: dict[str, Any] = {}
    for name, value in inspect.getmembers(proto):
        if name.startswith('_'):
            continue
        if inspect.isfunction(value) or inspect.ismethoddescriptor(value):
            required[name] = ('callable', inspect.signature(value))
        elif isinstance(value, property):
            required[name] = ('property', get_type_hints(value.fget).get('return', Any))
        else:
            required[name] = ('attr', get_type_hints(proto).get(name, Any))

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

    missing = [n for n in required if n not in provided]
    if missing:
        is_mismatch = True
        report.append('Missing members required by the Protocol:')
        for n in missing:
            report.append(f'  - {n}')
    else:
        report.append('All required members are present.')

    for name, (kind, req_sig) in required.items():
        if name not in provided:
            continue
        prov_kind, prov_sig = provided[name]
        if kind != prov_kind:
            report.append(f'Kind mismatch for {name}: protocol expects {kind}, class has {prov_kind}')
            is_mismatch = True
            continue
        if kind == 'callable':
            req_params = list(req_sig.params.values())
            prov_params = list(prov_sig.params.values())
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
            if req_sig != prov_sig:
                report.append(f'Type mismatch for property {name}: protocol says {req_sig}, class has {prov_sig}')
                is_mismatch = True
    result = '\r\n'.join(report)
    if is_mismatch:
        raise AssertionError(result)
    return result


@theory
@inlinedata(ClickHouseDBAPIConnection, DbConnection)
@inlinedata(ClickHouseDBAPIConnection, DbContext)
@inlinedata(ClickHouseProxyCursor, DbCursor)
@inlinedata(ClickHouseTransactionContext, DbTransactionContext)
@inlinedata(ClickHouseTypeMapper, DbTypeMapper)
def protocols_runtime_test(candidate: type, proto: type) -> None:
    """Assert various types can be runtime-checked for their equivalent Protocol(s)"""
    if not issubclass(candidate, proto):
        print(__protocol_mismatch_report(proto, candidate))
