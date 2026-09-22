# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from deev.entities import entity, field
from deev.translation import hydrate, splat
from deev.translation.utils import to_bsonobject
from punit import fact


class Color(Enum):
    RED = 'red'
    GREEN = 'green'
    BLUE = 'blue'


@fact
def splat_to_dict_serializes_uuid_to_string_for_json() -> None:
    """Verify splat converts UUID to string so the dict is JSON-serializable."""

    @entity
    class TestEntity:
        id: UUID = field(primary_key=True)
        value: str = ''

    entity1 = TestEntity(id=uuid4(), value='hello')
    d = splat(entity1, to_sql=False)
    assert 'id' in d
    assert isinstance(d['id'], str), f'id should be str for JSON, got {type(d["id"])}'


@fact
def splat_to_dict_serializes_datetime_to_iso_for_json() -> None:
    """Verify splat converts datetime to ISO string so the dict is JSON-serializable."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        created_at: datetime = datetime.now(timezone.utc)

    entity1 = TestEntity(id='test-1', created_at=datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone.utc))
    d = splat(entity1, to_sql=False)
    assert 'created_at' in d
    assert isinstance(d['created_at'], str), f'created_at should be str for JSON, got {type(d["created_at"])}'


@fact
def splat_to_dict_serializes_decimal_to_string_for_json() -> None:
    """Verify splat converts Decimal to string so the dict is JSON-serializable."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        price: Decimal = Decimal('0.00')

    entity1 = TestEntity(id='test-1', price=Decimal('19.99'))
    d = splat(entity1, to_sql=False)
    assert 'price' in d
    assert isinstance(d['price'], str), f'price should be str for JSON, got {type(d["price"])}'


@fact
def splat_to_dict_serializes_enum_to_value_for_json() -> None:
    """Verify splat converts Enum members to their value for JSON."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        color: Color = Color.RED

    entity1 = TestEntity(id='test-1', color=Color.BLUE)
    d = splat(entity1, to_sql=False)
    assert 'color' in d
    assert isinstance(d['color'], str), f'color should be str for JSON, got {type(d["color"])}'
    assert d['color'] == 'blue'


@fact
def json_roundtrip_splat_dict_preserves_uuid() -> None:
    """splat → dict → json serialize → json deserialize → dict should preserve UUID as string."""
    import json

    @entity
    class TestEntity:
        id: UUID = field(primary_key=True)
        value: str = ''

    entity1 = TestEntity(id=uuid4(), value='payload')
    original_id = entity1.id

    d = splat(entity1, to_sql=False)
    json_str = json.dumps(d)
    d_restored = json.loads(json_str)

    assert 'id' in d_restored
    assert d_restored['id'] == str(original_id)
    assert d_restored['value'] == 'payload'


@fact
def json_roundtrip_splat_dict_preserves_datetime() -> None:
    """splat → dict → json serialize → json deserialize → dict should preserve datetime as ISO string."""
    import json

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        ts: datetime = datetime.now(timezone.utc)

    ts = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
    entity1 = TestEntity(id='test-ts', ts=ts)
    d = splat(entity1, to_sql=False)
    json_str = json.dumps(d)
    d_restored = json.loads(json_str)

    assert 'ts' in d_restored
    # _to_json_value format: YYYY-MM-DDTHH:MM:SSZ (with or without microseconds)
    assert d_restored['ts'].startswith('2024-06-15')
    assert '10:30:00' in d_restored['ts']
    assert d_restored['ts'].endswith('Z')


@fact
def json_roundtrip_splat_dict_preserves_decimal() -> None:
    """splat → dict → json serialize → json deserialize → dict should preserve Decimal as string."""
    import json

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        amount: Decimal = Decimal('0.00')

    entity1 = TestEntity(id='test-dec', amount=Decimal('123.45'))
    d = splat(entity1, to_sql=False)
    json_str = json.dumps(d)
    d_restored = json.loads(json_str)

    assert 'amount' in d_restored
    assert d_restored['amount'] == '123.45'


@fact
def hydrate_from_dict_reconstructs_uuid_from_string() -> None:
    """hydrate should convert string UUID back to UUID object."""

    @entity
    class TestEntity:
        id: UUID = field(primary_key=True)
        value: str = ''

    original_id = uuid4()
    d = {'id': str(original_id), 'value': 'payload'}
    entity2 = hydrate(TestEntity, d, from_sql=False)

    assert isinstance(entity2.id, UUID)
    assert entity2.id == original_id
    assert entity2.value == 'payload'


@fact
def hydrate_from_dict_reconstructs_datetime_from_string() -> None:
    """hydrate should convert ISO string datetime back to datetime object."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        ts: datetime = datetime.now(timezone.utc)

    ts = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
    d = {'id': 'test', 'ts': ts.isoformat()}
    entity2 = hydrate(TestEntity, d, from_sql=False)

    assert isinstance(entity2.ts, datetime)
    assert entity2.ts == ts


@fact
def hydrate_from_dict_reconstructs_decimal_from_string() -> None:
    """hydrate should convert string Decimal back to Decimal object."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        amount: Decimal = Decimal('0.00')

    d = {'id': 'test', 'amount': '123.45'}
    entity2 = hydrate(TestEntity, d, from_sql=False)

    assert isinstance(entity2.amount, Decimal)
    assert entity2.amount == Decimal('123.45')


@fact
def splat_hydrate_roundtrip_entity_matches_original() -> None:
    """Full roundtrip: create entity → splat → json serialize → json deserialize → hydrate → should match."""
    import json

    @entity
    class TestEntity:
        id: UUID = field(primary_key=True)
        name: str = ''
        price: Decimal = Decimal('0.00')
        created: datetime = datetime.now(timezone.utc)
        color: Color = Color.RED

    original_id = uuid4()
    original_created = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
    entity1 = TestEntity(
        id=original_id,
        name='test entity',
        price=Decimal('99.99'),
        created=original_created,
        color=Color.BLUE,
    )

    d = splat(entity1, to_sql=False)
    json_str = json.dumps(d)
    d_restored = json.loads(json_str)
    entity2 = hydrate(TestEntity, d_restored, from_sql=False)

    assert isinstance(entity2.id, UUID), f'id should be UUID, got {type(entity2.id)}'
    assert entity2.id == original_id
    assert entity2.name == 'test entity'
    assert isinstance(entity2.price, Decimal)
    assert entity2.price == Decimal('99.99')
    assert isinstance(entity2.created, datetime)
    assert entity2.created == original_created
    assert isinstance(entity2.color, Color)
    assert entity2.color == Color.BLUE


@fact
def splat_hydrate_roundtrip_with_nullable_fields() -> None:
    """Roundtrip with nullable fields that are None should preserve None."""
    import json

    @entity
    class TestEntity:
        id: UUID = field(primary_key=True)
        optional_name: str | None = None
        optional_price: Decimal | None = None

    original_id = uuid4()
    entity1 = TestEntity(id=original_id, optional_name=None, optional_price=None)

    d = splat(entity1, to_sql=False)
    json_str = json.dumps(d)
    d_restored = json.loads(json_str)
    entity2 = hydrate(TestEntity, d_restored, from_sql=False)

    assert entity2.id == original_id
    assert entity2.optional_name is None
    assert entity2.optional_price is None


@fact
def splat_hydrate_roundtrip_with_non_null_nullable_fields() -> None:
    """Roundtrip with nullable fields that have values should preserve values."""
    import json

    @entity
    class TestEntity:
        id: UUID = field(primary_key=True)
        optional_name: str | None = None
        optional_price: Decimal | None = None

    original_id = uuid4()
    entity1 = TestEntity(id=original_id, optional_name='test', optional_price=Decimal('10.00'))

    d = splat(entity1, to_sql=False)
    json_str = json.dumps(d)
    d_restored = json.loads(json_str)
    entity2 = hydrate(TestEntity, d_restored, from_sql=False)

    assert entity2.id == original_id
    assert entity2.optional_name == 'test'
    assert isinstance(entity2.optional_price, Decimal)
    assert entity2.optional_price == Decimal('10.00')


@fact
def splat_hydrate_roundtrip_with_date_time_fields() -> None:
    """Roundtrip with date and time fields."""
    import json

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        birth_date: date = date.today()
        birth_time: time = time(12, 0, 0)

    original_date = date(1990, 5, 15)
    original_time = time(14, 30, 0)
    entity1 = TestEntity(id='test-1', birth_date=original_date, birth_time=original_time)

    d = splat(entity1, to_sql=False)
    json_str = json.dumps(d)
    d_restored = json.loads(json_str)
    entity2 = hydrate(TestEntity, d_restored, from_sql=False)

    assert entity2.id == 'test-1'
    assert isinstance(entity2.birth_date, date)
    assert entity2.birth_date == original_date
    assert isinstance(entity2.birth_time, time)
    assert entity2.birth_time == original_time


@fact
def splat_dict_contains_only_mapped_fields() -> None:
    """Verify splat returns only fields that are mapped (mapped=True or not set)."""

    @entity
    class TestEntity:
        id: UUID = field(primary_key=True, mapped=True)
        computed: str = field(default='x', mapped=False)

    entity1 = TestEntity(id=uuid4(), computed='ignored')
    d = splat(entity1, to_sql=False)
    assert 'id' in d
    assert 'computed' not in d


@fact
def splat_to_dict_serializes_timedelta_to_microseconds_int() -> None:
    """Verify splat converts timedelta to microseconds as int for JSON."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        duration: timedelta = timedelta(seconds=0)

    entity1 = TestEntity(id='test-1', duration=timedelta(days=1, hours=2, minutes=3, seconds=4, microseconds=5))
    d = splat(entity1, to_sql=False)
    assert 'duration' in d, f'duration should be in dict, got {list(d.keys())}'
    assert isinstance(d['duration'], int), f'duration should be int for JSON, got {type(d["duration"])}'
    expected_microseconds = 1 * 86_400_000_000 + 2 * 3_600_000_000 + 3 * 60_000_000 + 4 * 1_000_000 + 5
    assert d['duration'] == expected_microseconds, f'expected {expected_microseconds}, got {d["duration"]}'


@fact
def json_roundtrip_splat_dict_preserves_timedelta() -> None:
    """splat → dict → json serialize → json deserialize → dict should preserve timedelta as microseconds int."""
    import json

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        duration: timedelta = timedelta(seconds=0)

    original_duration = timedelta(days=3, hours=7, minutes=13, seconds=42, microseconds=999)
    entity1 = TestEntity(id='test-timedelta', duration=original_duration)
    d = splat(entity1, to_sql=False)
    json_str = json.dumps(d)
    d_restored = json.loads(json_str)

    assert 'duration' in d_restored, f'duration should be in restored dict, got {list(d_restored.keys())}'
    assert isinstance(d_restored['duration'], int), f'duration should be int, got {type(d_restored["duration"])}'
    assert d_restored['duration'] == 3 * 86_400_000_000 + 7 * 3_600_000_000 + 13 * 60_000_000 + 42 * 1_000_000 + 999


@fact
def hydrate_from_dict_reconstructs_timedelta_from_int() -> None:
    """hydrate should convert microseconds int back to timedelta object."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        duration: timedelta = timedelta(seconds=0)

    original_duration = timedelta(days=2, hours=5, minutes=10, seconds=20, microseconds=500)
    expected_microseconds = 2 * 86_400_000_000 + 5 * 3_600_000_000 + 10 * 60_000_000 + 20 * 1_000_000 + 500
    d = {'id': 'test', 'duration': expected_microseconds}
    entity2 = hydrate(TestEntity, d, from_sql=False)

    assert isinstance(entity2.duration, timedelta), f'duration should be timedelta, got {type(entity2.duration)}'
    assert entity2.duration == original_duration, f'expected {original_duration}, got {entity2.duration}'


@fact
def splat_hydrate_roundtrip_entity_with_timedelta() -> None:
    """Full roundtrip with timedelta: create entity → splat → json serialize → json deserialize → hydrate → should match."""
    import json

    @entity
    class TestEntity:
        id: UUID = field(primary_key=True)
        name: str = ''
        duration: timedelta = timedelta()

    original_id = uuid4()
    original_duration = timedelta(days=1, hours=1, minutes=1, seconds=1, microseconds=1)
    entity1 = TestEntity(id=original_id, name='timedelta entity', duration=original_duration)

    d = splat(entity1, to_sql=False)
    json_str = json.dumps(d)
    d_restored = json.loads(json_str)
    entity2 = hydrate(TestEntity, d_restored, from_sql=False)

    assert isinstance(entity2.duration, timedelta), f'duration should be timedelta, got {type(entity2.duration)}'
    assert entity2.duration == original_duration, f'expected {original_duration}, got {entity2.duration}'
    assert entity2.name == 'timedelta entity', f'expected "timedelta entity", got "{entity2.name}"'
    assert entity2.id == original_id, f'expected {original_id}, got {entity2.id}'


@fact
def splat_hydrate_roundtrip_with_nullable_timedelta() -> None:
    """Roundtrip with nullable timedelta field that is None should preserve None."""
    import json

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        optional_duration: timedelta | None = None

    entity1 = TestEntity(id='test-null', optional_duration=None)

    d = splat(entity1, to_sql=False)
    json_str = json.dumps(d)
    d_restored = json.loads(json_str)
    entity2 = hydrate(TestEntity, d_restored, from_sql=False)

    assert entity2.optional_duration is None, f'expected None, got {entity2.optional_duration}'


@fact
def splat_hydrate_roundtrip_with_zero_timedelta() -> None:
    """Roundtrip with zero timedelta should preserve zero duration."""
    import json

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        duration: timedelta = timedelta(days=1)

    entity1 = TestEntity(id='test-zero', duration=timedelta(seconds=0))

    d = splat(entity1, to_sql=False)
    json_str = json.dumps(d)
    d_restored = json.loads(json_str)
    entity2 = hydrate(TestEntity, d_restored, from_sql=False)

    assert isinstance(entity2.duration, timedelta), f'duration should be timedelta, got {type(entity2.duration)}'
    assert entity2.duration == timedelta(seconds=0), f'expected zero timedelta, got {entity2.duration}'


@fact
def splat_hydrate_roundtrip_with_negative_timedelta() -> None:
    """Roundtrip with negative timedelta should preserve negative duration."""
    import json

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        duration: timedelta = timedelta(seconds=0)

    original_duration = timedelta(days=-1, hours=-2, minutes=-3)
    entity1 = TestEntity(id='test-negative', duration=original_duration)

    d = splat(entity1, to_sql=False)
    json_str = json.dumps(d)
    d_restored = json.loads(json_str)
    entity2 = hydrate(TestEntity, d_restored, from_sql=False)

    assert isinstance(entity2.duration, timedelta), f'duration should be timedelta, got {type(entity2.duration)}'
    assert entity2.duration == original_duration, f'expected {original_duration}, got {entity2.duration}'


@fact
def to_bsonobject_serializes_timedelta_to_microseconds_int() -> None:
    """Verify to_bsonobject converts timedelta to microseconds as int for BSON."""
    td = timedelta(days=1, hours=2, minutes=3, seconds=4, microseconds=5)
    result = to_bsonobject(td)
    assert isinstance(result, int), f'to_bsonobject should return int, got {type(result)}'
    expected = 1 * 86_400_000_000 + 2 * 3_600_000_000 + 3 * 60_000_000 + 4 * 1_000_000 + 5
    assert result == expected, f'expected {expected}, got {result}'


@fact
def splat_to_bson_serializes_timedelta_to_int() -> None:
    """Verify splat with to_bson=True converts timedelta to microseconds int."""

    @entity
    class TestEntity:
        id: UUID = field(primary_key=True)
        duration: timedelta = timedelta(seconds=0)

    entity1 = TestEntity(id=uuid4(), duration=timedelta(days=1, hours=2, minutes=3, seconds=4, microseconds=5))
    d = splat(entity1, to_bson=True)
    assert 'duration' in d, f'duration should be in dict, got {list(d.keys())}'
    assert isinstance(d['duration'], int), f'duration should be int for BSON, got {type(d["duration"])}'


@fact
def splat_to_bson_preserves_uuid_as_uuid_object() -> None:
    """Verify splat with to_bson=True keeps UUID as UUID object (not string)."""

    @entity
    class TestEntity:
        id: UUID = field(primary_key=True)
        value: str = ''

    entity1 = TestEntity(id=uuid4(), value='hello')
    d = splat(entity1, to_bson=True)
    assert 'id' in d, f'id should be in dict, got {list(d.keys())}'
    assert isinstance(d['id'], UUID), f'id should be UUID for BSON, got {type(d["id"])}'


@fact
def splat_to_bson_converts_set_to_list() -> None:
    """Verify splat with to_bson=True converts set to list."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        tags: set[str] = field(default=set())

    entity1 = TestEntity(id='test-set', tags={'a', 'b', 'c'})
    d = splat(entity1, to_bson=True)
    assert 'tags' in d, f'tags should be in dict, got {list(d.keys())}'
    assert isinstance(d['tags'], list), f'tags should be list for BSON, got {type(d["tags"])}'


@fact
def splat_to_bson_with_timedelta_and_uuid() -> None:
    """Verify splat with to_bson=True handles timedelta + UUID together."""

    @entity
    class TestEntity:
        id: UUID = field(primary_key=True)
        duration: timedelta = timedelta(seconds=0)
        name: str = ''

    original_id = uuid4()
    original_duration = timedelta(hours=1, minutes=30)
    entity1 = TestEntity(id=original_id, duration=original_duration, name='test')
    d = splat(entity1, to_bson=True)
    assert isinstance(d['id'], UUID), f'id should be UUID, got {type(d["id"])}'
    assert d['id'] == original_id
    assert isinstance(d['duration'], int), f'duration should be int, got {type(d["duration"])}'
    assert d['name'] == 'test'


@fact
def hydrate_from_bson_reconstructs_timedelta_from_int() -> None:
    """Verify hydrate with from_bson=True converts int back to timedelta."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        duration: timedelta = timedelta(seconds=0)

    original_duration = timedelta(days=2, hours=5, minutes=10, seconds=20, microseconds=500)
    expected_microseconds = 2 * 86_400_000_000 + 5 * 3_600_000_000 + 10 * 60_000_000 + 20 * 1_000_000 + 500
    d = {'id': 'test', 'duration': expected_microseconds}
    entity2 = hydrate(TestEntity, d, from_bson=True)

    assert isinstance(entity2.duration, timedelta), f'duration should be timedelta, got {type(entity2.duration)}'
    assert entity2.duration == original_duration, f'expected {original_duration}, got {entity2.duration}'


@fact
def splat_hydrate_bson_roundtrip_timedelta() -> None:
    """Full BSON roundtrip: entity → splat(to_bson) → hydrate(from_bson) → should match."""

    @entity
    class TestEntity:
        id: UUID = field(primary_key=True)
        name: str = ''
        duration: timedelta = timedelta(seconds=0)

    original_id = uuid4()
    original_duration = timedelta(days=1, hours=1, minutes=1, seconds=1, microseconds=1)
    entity1 = TestEntity(id=original_id, name='bson entity', duration=original_duration)

    d = splat(entity1, to_bson=True)
    entity2 = hydrate(TestEntity, d, from_bson=True)

    assert isinstance(entity2.id, UUID), f'id should be UUID, got {type(entity2.id)}'
    assert entity2.id == original_id
    assert entity2.name == 'bson entity'
    assert isinstance(entity2.duration, timedelta), f'duration should be timedelta, got {type(entity2.duration)}'
    assert entity2.duration == original_duration, f'expected {original_duration}, got {entity2.duration}'


@fact
def splat_hydrate_bson_roundtrip_timedelta_zero() -> None:
    """BSON roundtrip with zero timedelta."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        duration: timedelta = timedelta(days=1)

    entity1 = TestEntity(id='test-zero', duration=timedelta(seconds=0))

    d = splat(entity1, to_bson=True)
    entity2 = hydrate(TestEntity, d, from_bson=True)

    assert isinstance(entity2.duration, timedelta), f'duration should be timedelta, got {type(entity2.duration)}'
    assert entity2.duration == timedelta(seconds=0), f'expected zero timedelta, got {entity2.duration}'


@fact
def splat_hydrate_bson_roundtrip_timedelta_negative() -> None:
    """BSON roundtrip with negative timedelta."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        duration: timedelta = timedelta(seconds=0)

    original_duration = timedelta(days=-1, hours=-2, minutes=-3)
    entity1 = TestEntity(id='test-negative', duration=original_duration)

    d = splat(entity1, to_bson=True)
    entity2 = hydrate(TestEntity, d, from_bson=True)

    assert isinstance(entity2.duration, timedelta), f'duration should be timedelta, got {type(entity2.duration)}'
    assert entity2.duration == original_duration, f'expected {original_duration}, got {entity2.duration}'


@fact
def splat_hydrate_bson_roundtrip_timedelta_nullable_none() -> None:
    """BSON roundtrip with nullable timedelta that is None."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        optional_duration: timedelta | None = None

    entity1 = TestEntity(id='test-null', optional_duration=None)

    d = splat(entity1, to_bson=True)
    entity2 = hydrate(TestEntity, d, from_bson=True)

    assert entity2.optional_duration is None, f'expected None, got {entity2.optional_duration}'


@fact
def to_bsonobject_handles_all_complex_types() -> None:
    """Verify to_bsonobject handles all complex types correctly."""
    original_uuid = uuid4()
    original_datetime = datetime(2024, 6, 15, 10, 30, 45, tzinfo=timezone.utc)
    original_date = date(2024, 6, 15)
    original_time = time(10, 30, 45)
    original_decimal = Decimal('123.45')
    original_timedelta = timedelta(days=1, hours=2, minutes=3)
    original_enum = Color.BLUE
    original_set = {'a', 'b'}

    assert isinstance(to_bsonobject(original_uuid), UUID)
    assert isinstance(to_bsonobject(original_datetime), datetime)
    assert to_bsonobject(original_date) == datetime(2024, 6, 15, 0, 0, 0)
    assert isinstance(to_bsonobject(original_time), str)
    assert isinstance(to_bsonobject(original_decimal), str)
    assert isinstance(to_bsonobject(original_timedelta), int)
    assert to_bsonobject(original_enum) == 'blue'
    assert isinstance(to_bsonobject(original_set), list)


# ===========================================================================
# BSON datetime/date/time unit tests
# ===========================================================================


@fact
def to_bsonobject_passes_aware_datetime_through() -> None:
    """to_bsonobject should pass through datetime with tzinfo as-is (BSON native Date)."""
    original = datetime(2024, 6, 15, 10, 30, 45, 123456, tzinfo=timezone.utc)
    result = to_bsonobject(original)
    assert result is original, 'aware datetime should pass through as same object'
    assert isinstance(result, datetime)


@fact
def to_bsonobject_passes_naive_datetime_through() -> None:
    """to_bsonobject should pass through naive datetime as-is (BSON stores it natively)."""
    original = datetime(2024, 6, 15, 10, 30, 0)
    result = to_bsonobject(original)
    assert result is original, 'naive datetime should pass through as same object'
    assert isinstance(result, datetime)


@fact
def to_bsonobject_converts_date_to_midnight_datetime() -> None:
    """to_bsonobject should convert date to a midnight datetime (BSON has no date-only type)."""
    original = date(2024, 6, 15)
    result = to_bsonobject(original)
    assert isinstance(result, datetime), f'date should become datetime, got {type(result)}'
    assert result == datetime(2024, 6, 15, 0, 0, 0), f'expected midnight, got {result}'
    assert result.year == 2024 and result.month == 6 and result.day == 15


@fact
def to_bsonobject_converts_time_to_iso_string_with_microseconds() -> None:
    """to_bsonobject should convert time to ISO string with microseconds."""
    original = time(9, 30, 45, 123456)
    result = to_bsonobject(original)
    assert isinstance(result, str), f'time should become str, got {type(result)}'
    assert result == '09:30:45.123456', f'expected "09:30:45.123456", got {result}'


@fact
def to_bsonobject_converts_time_to_iso_string_without_microseconds() -> None:
    """to_bsonobject should convert time without microseconds to clean ISO string."""
    original = time(14, 0, 0)
    result = to_bsonobject(original)
    assert isinstance(result, str)
    assert result == '14:00:00', f'expected "14:00:00", got {result}'


@fact
def to_bsonobject_converts_time_without_seconds() -> None:
    """to_bsonobject should convert time with no seconds/microseconds."""
    original = time(12, 0)
    result = to_bsonobject(original)
    assert isinstance(result, str)
    assert result == '12:00:00', f'expected "12:00:00", got {result}'


@fact
def to_bsonobject_converts_datetime_date_time_together() -> None:
    """to_bsonobject should handle datetime, date, and time in the same call."""
    dt = datetime(2024, 6, 15, 10, 30, 45, tzinfo=timezone.utc)
    d = date(2024, 6, 15)
    t = time(14, 30, 45, 999999)
    assert isinstance(to_bsonobject(dt), datetime)
    assert to_bsonobject(d) == datetime(2024, 6, 15, 0, 0, 0)
    assert to_bsonobject(t) == '14:30:45.999999'


@fact
def to_bsonobject_none_value_returns_none() -> None:
    """to_bsonobject(None) should return None."""
    assert to_bsonobject(None) is None


# ===========================================================================
# splat/to_bson datetime/date/time tests
# ===========================================================================


@fact
def splat_to_bson_serializes_datetime_field_as_datetime() -> None:
    """splat(entity, to_bson=True) should keep datetime field as datetime object."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        ts: datetime = datetime.now(timezone.utc)

    ts = datetime(2024, 6, 15, 10, 30, 45, 123456, tzinfo=timezone.utc)
    entity1 = TestEntity(id='test', ts=ts)
    d = splat(entity1, to_bson=True)
    assert isinstance(d['ts'], datetime), f'ts should be datetime, got {type(d["ts"])}'
    assert d['ts'] is ts, 'datetime should pass through as same object'


@fact
def splat_to_bson_serializes_naive_datetime_field_as_datetime() -> None:
    """splat with naive datetime should keep it as datetime."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        ts: datetime = datetime.now()

    ts = datetime(2024, 6, 15, 10, 30, 0)
    entity1 = TestEntity(id='test', ts=ts)
    d = splat(entity1, to_bson=True)
    assert isinstance(d['ts'], datetime), f'ts should be datetime, got {type(d["ts"])}'
    assert d['ts'] is ts


@fact
def splat_to_bson_serializes_date_field_as_datetime() -> None:
    """splat(entity, to_bson=True) should convert date field to midnight datetime."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        birth_date: date = date.today()

    d = date(1990, 5, 15)
    entity1 = TestEntity(id='test', birth_date=d)
    d_out = splat(entity1, to_bson=True)
    assert isinstance(d_out['birth_date'], datetime), f'birth_date should be datetime, got {type(d_out["birth_date"])}'
    assert d_out['birth_date'] == datetime(1990, 5, 15, 0, 0, 0)


@fact
def splat_to_bson_serializes_time_field_as_iso_string() -> None:
    """splat(entity, to_bson=True) should convert time field to ISO string."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        alarm_time: time = time(7, 0, 0)

    t = time(8, 30, 45, 123456)
    entity1 = TestEntity(id='test', alarm_time=t)
    d_out = splat(entity1, to_bson=True)
    assert isinstance(d_out['alarm_time'], str), f'alarm_time should be str, got {type(d_out["alarm_time"])}'
    assert d_out['alarm_time'] == '08:30:45.123456'


@fact
def splat_to_bson_serializes_time_field_without_microseconds() -> None:
    """splat with time without microseconds should produce clean ISO string."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        start: time = time(0, 0, 0)

    t = time(9, 0, 0)
    entity1 = TestEntity(id='test', start=t)
    d_out = splat(entity1, to_bson=True)
    assert d_out['start'] == '09:00:00'


@fact
def splat_to_bson_with_datetime_date_time_all_fields() -> None:
    """splat with all three types in one entity should serialize each correctly."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        ts: datetime = datetime.now(timezone.utc)
        birth_date: date = date.today()
        alarm: time = time(0, 0, 0)

    dt = datetime(2024, 6, 15, 10, 30, 45, 123456, tzinfo=timezone.utc)
    d = date(1990, 5, 15)
    t = time(14, 30, 0)
    entity1 = TestEntity(id='test', ts=dt, birth_date=d, alarm=t)
    d_out = splat(entity1, to_bson=True)
    assert isinstance(d_out['ts'], datetime)
    assert d_out['ts'] is dt
    assert isinstance(d_out['birth_date'], datetime)
    assert d_out['birth_date'] == datetime(1990, 5, 15, 0, 0, 0)
    assert d_out['alarm'] == '14:30:00'


# ===========================================================================
# hydrate/from_bson datetime/date/time tests
# ===========================================================================


@fact
def hydrate_from_bson_reconstructs_datetime_from_native() -> None:
    """hydrate(from_bson=True) should accept native datetime for datetime field."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        ts: datetime = datetime.now(timezone.utc)

    original = datetime(2024, 6, 15, 10, 30, 45, 123456, tzinfo=timezone.utc)
    d = {'id': 'test', 'ts': original}
    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert isinstance(entity2.ts, datetime)
    assert entity2.ts is original


@fact
def hydrate_from_bson_reconstructs_datetime_from_iso_string() -> None:
    """hydrate(from_bson=True) should convert ISO string back to datetime (legacy path)."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        ts: datetime = datetime.now(timezone.utc)

    d = {'id': 'test', 'ts': '2024-06-15T10:30:45.000000Z'}
    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert isinstance(entity2.ts, datetime)
    assert entity2.ts.year == 2024 and entity2.ts.month == 6 and entity2.ts.day == 15


@fact
def hydrate_from_bson_reconstructs_date_from_midnight_datetime() -> None:
    """hydrate(from_bson=True) should extract .date() from midnight datetime for date field."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        birth_date: date = date.today()

    stored = datetime(1990, 5, 15, 0, 0, 0)
    d = {'id': 'test', 'birth_date': stored}
    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert isinstance(entity2.birth_date, date), f'birth_date should be date, got {type(entity2.birth_date)}'
    assert entity2.birth_date == date(1990, 5, 15)
    assert not isinstance(entity2.birth_date, datetime)


@fact
def hydrate_from_bson_reconstructs_date_from_string_legacy() -> None:
    """hydrate(from_bson=True) should parse ISO string for date field (legacy/edge case)."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        birth_date: date = date.today()

    d = {'id': 'test', 'birth_date': '1990-05-15'}
    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert isinstance(entity2.birth_date, date)
    assert entity2.birth_date == date(1990, 5, 15)


@fact
def hydrate_from_bson_reconstructs_time_from_iso_string() -> None:
    """hydrate(from_bson=True) should parse ISO string back to time for time field."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        alarm: time = time(0, 0, 0)

    d = {'id': 'test', 'alarm': '08:30:45.123456'}
    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert isinstance(entity2.alarm, time), f'alarm should be time, got {type(entity2.alarm)}'
    assert entity2.alarm == time(8, 30, 45, 123456)


@fact
def hydrate_from_bson_reconstructs_time_without_microseconds() -> None:
    """hydrate(from_bson=True) should parse ISO string without microseconds for time field."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        alarm: time = time(0, 0, 0)

    d = {'id': 'test', 'alarm': '14:00:00'}
    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert isinstance(entity2.alarm, time)
    assert entity2.alarm == time(14, 0, 0)


@fact
def hydrate_from_bson_reconstructs_time_from_native_time() -> None:
    """hydrate(from_bson=True) should pass through native time for time field (edge case)."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        alarm: time = time(0, 0, 0)

    original = time(9, 30, 0)
    d = {'id': 'test', 'alarm': original}
    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert isinstance(entity2.alarm, time)
    assert entity2.alarm is original


# ===========================================================================
# Full roundtrip datetime/date/time tests
# ===========================================================================


@fact
def splat_hydrate_bson_roundtrip_datetime() -> None:
    """Full BSON roundtrip with datetime field: splat(to_bson) → hydrate(from_bson)."""

    @entity
    class TestEntity:
        id: UUID = field(primary_key=True)
        name: str = ''
        created: datetime = datetime.now(timezone.utc)

    original_id = uuid4()
    original_created = datetime(2024, 6, 15, 10, 30, 45, 123456, tzinfo=timezone.utc)
    entity1 = TestEntity(id=original_id, name='test', created=original_created)

    d = splat(entity1, to_bson=True)
    entity2 = hydrate(TestEntity, d, from_bson=True)

    assert isinstance(entity2.id, UUID)
    assert entity2.id == original_id
    assert entity2.name == 'test'
    assert isinstance(entity2.created, datetime)
    assert entity2.created is original_created


@fact
def splat_hydrate_bson_roundtrip_date() -> None:
    """Full BSON roundtrip with date field: splat(to_bson) → hydrate(from_bson)."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        name: str = ''
        birth_date: date = date.today()

    original_date = date(1990, 5, 15)
    entity1 = TestEntity(id='test', name='John', birth_date=original_date)

    d = splat(entity1, to_bson=True)
    assert isinstance(d['birth_date'], datetime), f'should store as datetime, got {type(d["birth_date"])}'
    assert d['birth_date'] == datetime(1990, 5, 15, 0, 0, 0)

    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert isinstance(entity2.birth_date, date), f'should hydrate as date, got {type(entity2.birth_date)}'
    assert entity2.birth_date == original_date
    assert not isinstance(entity2.birth_date, datetime)


@fact
def splat_hydrate_bson_roundtrip_time() -> None:
    """Full BSON roundtrip with time field: splat(to_bson) → hydrate(from_bson)."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        name: str = ''
        alarm: time = time(0, 0, 0)

    original_time = time(8, 30, 45, 123456)
    entity1 = TestEntity(id='test', name='alarm_clock', alarm=original_time)

    d = splat(entity1, to_bson=True)
    assert isinstance(d['alarm'], str), f'should store as str, got {type(d["alarm"])}'
    assert d['alarm'] == '08:30:45.123456'

    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert isinstance(entity2.alarm, time), f'should hydrate as time, got {type(entity2.alarm)}'
    assert entity2.alarm == original_time


@fact
def splat_hydrate_bson_roundtrip_datetime_date_time_all_together() -> None:
    """Full BSON roundtrip with all three date/time types in one entity."""

    @entity
    class TestEntity:
        id: UUID = field(primary_key=True)
        created: datetime = datetime.now(timezone.utc)
        birth_date: date = date.today()
        alarm: time = time(0, 0, 0)

    original_id = uuid4()
    original_dt = datetime(2024, 6, 15, 10, 30, 45, 123456, tzinfo=timezone.utc)
    original_d = date(1990, 5, 15)
    original_t = time(14, 30, 0)
    entity1 = TestEntity(id=original_id, created=original_dt, birth_date=original_d, alarm=original_t)

    d = splat(entity1, to_bson=True)
    assert isinstance(d['created'], datetime)
    assert d['created'] is original_dt
    assert isinstance(d['birth_date'], datetime)
    assert d['birth_date'] == datetime(1990, 5, 15, 0, 0, 0)
    assert d['alarm'] == '14:30:00'

    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert entity2.id == original_id
    assert entity2.created is original_dt
    assert entity2.birth_date == original_d
    assert not isinstance(entity2.birth_date, datetime)
    assert entity2.alarm == original_t


@fact
def splat_hydrate_bson_roundtrip_datetime_naive() -> None:
    """Full BSON roundtrip with naive datetime (no timezone)."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        ts: datetime = datetime.now()

    original = datetime(2024, 6, 15, 10, 30, 0)
    entity1 = TestEntity(id='test', ts=original)

    d = splat(entity1, to_bson=True)
    assert isinstance(d['ts'], datetime)
    assert d['ts'] is original

    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert entity2.ts == original.replace(tzinfo=timezone.utc)


@fact
def splat_hydrate_bson_roundtrip_time_without_microseconds() -> None:
    """Full BSON roundtrip with time that has no microseconds."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        start: time = time(0, 0, 0)

    original = time(9, 0, 0)
    entity1 = TestEntity(id='test', start=original)

    d = splat(entity1, to_bson=True)
    assert d['start'] == '09:00:00'

    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert entity2.start == original


# ===========================================================================
# Container type round-trips: list[date], list[time], tuple[date], tuple[time], dict[str, date], dict[str, time]
# ===========================================================================


@fact
def splat_hydrate_bson_roundtrip_list_of_dates() -> None:
    """list[date] → list[datetime] on splat → list[date] on hydrate."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        dates: list[date] = []

    original = [date(2024, 1, 15), date(2025, 6, 20), date(2023, 12, 25)]
    entity1 = TestEntity(id='ct-1', dates=original)

    d = splat(entity1, to_bson=True)
    assert d['dates'] == [datetime(2024, 1, 15), datetime(2025, 6, 20), datetime(2023, 12, 25)]

    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert entity2.dates == original


@fact
def splat_hydrate_bson_roundtrip_list_of_times() -> None:
    """list[time] → list[str] on splat → list[time] on hydrate."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        times: list[time] = []

    original = [time(8, 30, 0), time(14, 15, 30, 500000)]
    entity1 = TestEntity(id='ct-2', times=original)

    d = splat(entity1, to_bson=True)
    assert d['times'] == ['08:30:00', '14:15:30.500000']

    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert entity2.times == original


@fact
def splat_hydrate_bson_roundtrip_list_mixed_types() -> None:
    """list[date] with datetime values in the stored data should convert to date."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        dates: list[date] = []

    # Simulate data already in the database as datetime objects
    d = {
        '_id': 'ct-3',
        'dates': [datetime(2024, 1, 15), datetime(2025, 6, 20)]
    }

    res = hydrate(TestEntity, d, from_bson=True)
    assert res.dates == [date(2024, 1, 15), date(2025, 6, 20)]


@fact
def splat_hydrate_bson_roundtrip_tuple_of_dates() -> None:
    """tuple[date, ...] → tuple[datetime, ...] on splat → tuple[date, ...] on hydrate."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        dates: tuple[date, ...] = ()

    original = (date(2024, 3, 1), date(2025, 7, 15))
    entity1 = TestEntity(id='ct-4', dates=original)

    d = splat(entity1, to_bson=True)
    assert d['dates'] == (datetime(2024, 3, 1), datetime(2025, 7, 15))

    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert entity2.dates == original


@fact
def splat_hydrate_bson_roundtrip_tuple_of_times() -> None:
    """tuple[time, ...] → tuple[str, ...] on splat → tuple[time, ...] on hydrate."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        times: tuple[time, ...] = ()

    original = (time(9, 0, 0), time(17, 30, 0))
    entity1 = TestEntity(id='ct-5', times=original)

    d = splat(entity1, to_bson=True)
    assert d['times'] == ('09:00:00', '17:30:00')

    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert entity2.times == original


@fact
def splat_hydrate_bson_roundtrip_dict_of_dates() -> None:
    """dict[str, date] → dict[str, datetime] on splat → dict[str, date] on hydrate."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        events: dict[str, date] = {}

    original = {'meeting': date(2024, 6, 1), 'holiday': date(2024, 12, 25)}
    entity1 = TestEntity(id='ct-6', events=original)

    d = splat(entity1, to_bson=True)
    assert d['events'] == {'meeting': datetime(2024, 6, 1), 'holiday': datetime(2024, 12, 25)}

    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert entity2.events == original


@fact
def splat_hydrate_bson_roundtrip_dict_of_times() -> None:
    """dict[str, time] → dict[str, str] on splat → dict[str, time] on hydrate."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        alarms: dict[str, time] = {}

    original = {'wake_up': time(7, 0, 0), 'lunch': time(12, 0, 0)}
    entity1 = TestEntity(id='ct-7', alarms=original)

    d = splat(entity1, to_bson=True)
    assert d['alarms'] == {'wake_up': '07:00:00', 'lunch': '12:00:00'}

    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert entity2.alarms == original


@fact
def splat_to_bson_serializes_nested_list_of_dicts_with_dates() -> None:
    """Nested structures like list[dict[str, date]] serialize correctly."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        schedule: list[dict[str, date]] = []

    original = [{'day': date(2024, 1, 1)}, {'day': date(2024, 1, 2)}, {'day': date(2024, 1, 3)}]
    entity1 = TestEntity(id='ct-8', schedule=original)

    d = splat(entity1, to_bson=True)
    assert d['schedule'] == [
        {'day': datetime(2024, 1, 1)},
        {'day': datetime(2024, 1, 2)},
        {'day': datetime(2024, 1, 3)}
    ]

    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert entity2.schedule == original


@fact
def splat_to_bson_handles_empty_containers() -> None:
    """Empty containers serialize and deserialize correctly."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        dates: list[date] = []
        times: tuple[time, ...] = ()
        events: dict[str, date] = {}

    entity1 = TestEntity(id='ct-9')
    d = splat(entity1, to_bson=True)
    assert d['dates'] == []
    assert d['times'] == ()
    assert d['events'] == {}

    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert entity2.dates == []
    assert entity2.times == ()
    assert entity2.events == {}


@fact
def splat_to_bson_handles_none_in_containers() -> None:
    """None values inside containers are preserved."""

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        dates: list[date] = []

    original = [date(2024, 1, 1), None, date(2025, 1, 1)]
    entity1 = TestEntity(id='ct-10', dates=original)  # type: ignore[arg-type]

    d = splat(entity1, to_bson=True)
    assert d['dates'] == [datetime(2024, 1, 1), None, datetime(2025, 1, 1)]

    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert entity2.dates == [date(2024, 1, 1), None, date(2025, 1, 1)]


@fact
def splat_to_bson_list_any_roundtrip() -> None:
    """list[Any] — splat converts date/time via isinstance, hydrate returns as-is."""
    from typing import Any

    @entity
    class TestEntity:
        id: str = field(primary_key=True)
        items: list[Any] = []

    original = ['foo', date(2024, 1, 1), time(12, 30, 0), 42]
    entity1 = TestEntity(id='t1', items=original)

    d = splat(entity1, to_bson=True)
    assert d['items'] == ['foo', datetime(2024, 1, 1, 0, 0), '12:30:00', 42]

    # hydrate with list[Any] — since hint is Any, to_pyobject returns value as-is
    entity2 = hydrate(TestEntity, d, from_bson=True)
    assert entity2.items == ['foo', datetime(2024, 1, 1, 0, 0), '12:30:00', 42]
