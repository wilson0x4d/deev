# SPDX-FileCopyrightText: © 2026 Shaun Wilson
# SPDX-License-Identifier: MIT

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from deev.entities import entity, field
from deev.translation import hydrate, splat
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
        optional_name: Optional[str] = None
        optional_price: Optional[Decimal] = None

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
        optional_name: Optional[str] = None
        optional_price: Optional[Decimal] = None

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
