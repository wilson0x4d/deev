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

* Entity-based; perform CRUD operations using Python objects instead of
  hand-crafting SQL.
* Validation; Entities validate before they get persisted to a database, also validate entities on-demand.
* Transaction Contexts; enter and exit transaction scopes with language-level
  context management, avoid mismanaged transaction states.
* DB Migrations; use Python code to apply (and undo) schema changes, data
  translation, etc. using the ``db-migrate`` CLI tool for use from CI/CD
  pipelines.
* PEP 249 compatible abstractions; no need to refactor code just to switch
  DBMS.
* Syntax normalization; parameterize SQL using ``%?`` instead of
  provider-specific syntaxes.
* Raw SQL Access; execute raw SQL as-needed, including provider/DBMS-specific
  functions (primarily intended for advanced ``db-migrate`` cases).


Contents
--------

.. toctree::
   :maxdepth: 3

   Overview <self>
   Quick Start <quickstart>
   Reference <ref/index>
   MIT License <license>
   Contact <contact>
