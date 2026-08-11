Overview
========

.. image:: https://img.shields.io/pypi/v/deev.svg
   :target: https://pypi.org/project/deev/
   :alt: deev on PyPI

.. image:: https://readthedocs.org/projects/deev/badge/?version=latest
   :target: https://deev.readthedocs.io
   :alt: deev on Read the Docs

**deev** (דיב) is an entity framework for Python.


Features
========

- **Entity-based CRUD** — work with Python objects, not hand-crafted SQL.
- **Validation** — entities are validated before persistence and on-demand.
- **Transaction Contexts** — scope transactions with context managers, never leave a mismanaged state.
- **Migrations** — version-controlled schema and data migrations via the ``db-migrate`` CLI or programmatically via the ``DbMigrate`` class.
- **Multi-provider** — built-in providers for SQLite, MySQL, ClickHouse, and MongoDB.
- **PEP 249 compatibility** — switch DBMS without refactoring data access code.
- **Parameterized queries** — unified ``%?`` syntax across all providers.
- **Connection strings** — Supports both DSN URIs (``sqlite://``, ``mysql://``) and OLEDB-style strings.
- **Declarative indexes** — define composite, unique, and directional indexes on entity fields.
- **Native Interface Access** — drop down to provider-specific methods when the ORM layer isn't enough.


Contents
--------

.. toctree::
   :maxdepth: 3

   Overview <self>
   Quick Start <quickstart>
   Database Migration <migration>
   Reference <ref/index>
   SKILL <SKILL>
   MIT License <license>
   Contact <contact>
