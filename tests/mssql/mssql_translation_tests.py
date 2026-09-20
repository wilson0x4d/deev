# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, cast

from deev import entity, field
from deev.translation import splat, hydrate, to_mssql_object, to_pyobject, deunionize
from punit import fact, trait
from uuid import UUID, uuid4


# Helper to get the deunionized type for Optional/U[Union] hints
def _hint(t: Any) -> type:
    return deunionize(cast(type, t))


class TestToMssqlObject:
    @fact
    @trait('unit')
    def when_uuid_then_returns_hyphenated_string(self) -> None:
        target = uuid4()
        result = to_mssql_object(target, _hint(UUID | None))
        assert isinstance(result, str), f"(expected=str, actual={type(result).__name__})"
        assert '-' in result, f"expected hyphenated format, got: {result!r}"
        assert result == str(target), f"(expected={str(target)!r}, actual={result!r})"

    @fact
    @trait('unit')
    def when_uuid_is_none_then_returns_none(self) -> None:
        result = to_mssql_object(None, _hint(UUID | None))
        assert result is None, f"(expected=None, actual={result!r})"

    @fact
    @trait('unit')
    def when_datetime_with_tz_then_returns_utc_datetime(self) -> None:
        dt = datetime(2024, 6, 15, 14, 30, 0, tzinfo=timezone(timedelta(hours=-5)))
        result = to_mssql_object(dt, datetime)
        assert isinstance(result, datetime), f"(expected=datetime, actual={type(result).__name__})"
        assert result.tzinfo is not None, f"expected tzinfo, got None"
        assert result.hour == 19, f"expected 19 UTC, got {result.hour}"

    @fact
    @trait('unit')
    def when_datetime_without_tz_then_adds_utc(self) -> None:
        dt = datetime(2024, 6, 15, 14, 30, 0)
        result = to_mssql_object(dt, datetime)
        assert result.tzinfo is not None, f"expected tzinfo, got None"

    @fact
    @trait('unit')
    def when_bool_true_then_returns_int_one(self) -> None:
        result = to_mssql_object(True, bool)
        assert result == 1, f"(expected=1, actual={result!r})"

    @fact
    @trait('unit')
    def when_bool_false_then_returns_int_zero(self) -> None:
        result = to_mssql_object(False, bool)
        assert result == 0, f"(expected=0, actual={result!r})"

    @fact
    @trait('unit')
    def when_timedelta_then_returns_microseconds_int(self) -> None:
        td = timedelta(days=1, hours=2, minutes=3, seconds=4, microseconds=5)
        result = to_mssql_object(td, timedelta)
        expected = 86_400_000_000 + 7_200_000_000 + 180_000_000 + 4_000_000 + 5
        assert result == expected, f"(expected={expected}, actual={result!r})"

    @fact
    @trait('unit')
    def when_decimal_then_returns_decimal(self) -> None:
        d = Decimal('123.45')
        result = to_mssql_object(d, Decimal)
        assert isinstance(result, Decimal), f"(expected=Decimal, actual={type(result).__name__})"
        assert result == Decimal('123.45'), f"(expected=123.45, actual={result!r})"

    @fact
    @trait('unit')
    def when_dict_then_returns_json_string(self) -> None:
        data = {'key': 'value', 'num': 42}
        result = to_mssql_object(data, dict[str, Any])
        assert isinstance(result, str), f"(expected=str, actual={type(result).__name__})"

    @fact
    @trait('unit')
    def when_list_then_returns_json_string(self) -> None:
        data = [1, 2, 3]
        result = to_mssql_object(data, list[int])
        assert isinstance(result, str), f"(expected=str, actual={type(result).__name__})"


class TestSplatWithToMssql:
    @fact
    @trait('unit')
    def when_splat_with_to_mssql_uuid_becomes_hyphenated_string(self) -> None:
        @entity
        class Entity:
            id: int = field(primary_key=True)
            ref_uuid: UUID | None = None

        entity_inst = Entity(id=1, ref_uuid=uuid4())
        result = splat(entity_inst, to_mssql=True)

        assert result['id'] == 1, f"(expected=1, actual={result['id']!r})"
        assert isinstance(result['ref_uuid'], str), f"(expected=str, actual={type(result['ref_uuid']).__name__})"
        assert '-' in result['ref_uuid'], f"expected hyphenated format, got: {result['ref_uuid']!r}"

    @fact
    @trait('unit')
    def when_splat_with_to_mssql_does_not_mutate_entity(self) -> None:
        @entity
        class Entity:
            id: int = field(primary_key=True)
            ref_uuid: UUID | None = None

        target_uuid = uuid4()
        entity_inst = Entity(id=1, ref_uuid=target_uuid)
        assert isinstance(entity_inst.ref_uuid, UUID), f"entity should start with UUID, got {type(entity_inst.ref_uuid)}"

        result = splat(entity_inst, to_mssql=True)

        # After splat, the entity's UUID should still be a UUID, not a string
        assert isinstance(entity_inst.ref_uuid, UUID), (
            f"splat mutated the entity! ref_uuid is {type(entity_inst.ref_uuid).__name__} after splat"
        )
        assert entity_inst.ref_uuid == target_uuid, f"entity ref_uuid was mutated from {target_uuid} to {entity_inst.ref_uuid}"

    @fact
    @trait('unit')
    def when_splat_with_to_mssql_bool_becomes_int(self) -> None:
        @entity
        class Entity:
            id: int = field(primary_key=True)
            active: bool | None = None

        entity_inst = Entity(id=1, active=True)
        result = splat(entity_inst, to_mssql=True)
        assert result['active'] == 1, f"(expected=1, actual={result['active']!r})"

    @fact
    @trait('unit')
    def when_splat_with_to_mssql_datetime_keeps_utc_datetime(self) -> None:
        @entity
        class Entity:
            id: int = field(primary_key=True)
            created_at: datetime | None = None

        dt = datetime(2024, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
        entity_inst = Entity(id=1, created_at=dt)
        result = splat(entity_inst, to_mssql=True)
        assert isinstance(result['created_at'], datetime), f"(expected=datetime, actual={type(result['created_at']).__name__})"

    @fact
    @trait('unit')
    def when_splat_with_to_mssql_timedelta_becomes_int(self) -> None:
        @entity
        class Entity:
            id: int = field(primary_key=True)
            duration: timedelta | None = None

        entity_inst = Entity(id=1, duration=timedelta(hours=1))
        result = splat(entity_inst, to_mssql=True)
        assert isinstance(result['duration'], int), f"(expected=int, actual={type(result['duration']).__name__})"

    @fact
    @trait('unit')
    def when_splat_with_to_mssql_complex_types_become_json(self) -> None:
        @entity
        class Entity:
            id: int = field(primary_key=True)
            metadata: dict[str, Any] | None = None
            tags: list[str] | None = None

        entity_inst = Entity(id=1, metadata={'key': 'val'}, tags=['a', 'b'])
        result = splat(entity_inst, to_mssql=True)
        assert isinstance(result['metadata'], str), f"(expected=str, actual={type(result['metadata']).__name__})"
        assert isinstance(result['tags'], str), f"(expected=str, actual={type(result['tags']).__name__})"


class TestHydrateWithFromMssql:
    @fact
    @trait('unit')
    def when_hydrate_from_mssql_uuid_string_becomes_uuid(self) -> None:
        @entity
        class Entity:
            id: int = field(primary_key=True)
            ref_uuid: UUID | None = None

        data = {'id': 1, 'ref_uuid': str(uuid4())}
        entity_inst = hydrate(Entity, data, from_mssql=True)
        assert isinstance(entity_inst.ref_uuid, UUID), f"(expected=UUID, actual={type(entity_inst.ref_uuid).__name__})"

    @fact
    @trait('unit')
    def when_hydrate_from_mssql_uuid_hyphenated_string_becomes_uuid(self) -> None:
        @entity
        class Entity:
            id: int = field(primary_key=True)
            ref_uuid: UUID | None = None

        hyphenated = str(uuid4())
        assert '-' in hyphenated, "test needs hyphenated format"
        data = {'id': 1, 'ref_uuid': hyphenated}
        entity_inst = hydrate(Entity, data, from_mssql=True)
        assert isinstance(entity_inst.ref_uuid, UUID), f"(expected=UUID, actual={type(entity_inst.ref_uuid).__name__})"

    @fact
    @trait('unit')
    def when_hydrate_from_mssql_uuid_hex_string_becomes_uuid(self) -> None:
        """to_pyobject accepts both hyphenated and hex UUID strings — this covers the hex path."""
        @entity
        class Entity:
            id: int = field(primary_key=True)
            ref_uuid: UUID | None = None

        hex_str = uuid4().hex
        assert '-' not in hex_str, "test needs hex format"
        data = {'id': 1, 'ref_uuid': hex_str}
        entity_inst = hydrate(Entity, data, from_mssql=True)
        assert isinstance(entity_inst.ref_uuid, UUID), f"(expected=UUID, actual={type(entity_inst.ref_uuid).__name__})"

    @fact
    @trait('unit')
    def when_hydrate_from_mssql_optional_uuid_is_none(self) -> None:
        @entity
        class Entity:
            id: int = field(primary_key=True)
            ref_uuid: UUID | None = None

        data = {'id': 1, 'ref_uuid': None}
        entity_inst = hydrate(Entity, data, from_mssql=True)
        assert entity_inst.ref_uuid is None, f"(expected=None, actual={entity_inst.ref_uuid!r})"


class TestFullRoundTrip:
    @fact
    @trait('unit')
    def uuid_roundtrip_splat_to_mssql_then_hydrate_from_mssql(self) -> None:
        @entity
        class Entity:
            id: int = field(primary_key=True)
            ref_uuid: UUID | None = None

        target_uuid = uuid4()
        entity_inst = Entity(id=1, ref_uuid=target_uuid)

        # Step 1: splat with to_mssql (what MSSQL adapter does on write)
        sql_data = splat(entity_inst, to_mssql=True)
        assert sql_data['id'] == 1
        assert isinstance(sql_data['ref_uuid'], str)
        assert '-' in sql_data['ref_uuid'], "to_mssql should produce hyphenated UUID string"

        # Step 2: hydrate from mssql (what MSSQL adapter does on read)
        hydrated = hydrate(Entity, sql_data, from_mssql=True)
        assert isinstance(hydrated.ref_uuid, UUID), f"(expected=UUID, actual={type(hydrated.ref_uuid).__name__})"
        assert hydrated.ref_uuid == target_uuid, f"(expected={target_uuid}, actual={hydrated.ref_uuid})"

        # Step 3: entity was never mutated
        assert entity_inst.ref_uuid == target_uuid
