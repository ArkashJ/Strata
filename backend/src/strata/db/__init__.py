"""Database layer — SQLAlchemy 2.0 async + asyncpg.

Postgres mirror lands at v0.3 (see docs/07-data-layer-brainstorm.md Q27).
At v0.2 the data layer is YAML-on-disk; this module exists so the
infrastructure (engine, sessions, migrations) is wired and ready.
"""
