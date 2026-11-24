-- Migration 001: run health (Azure SQL)
--
-- For a database created from an earlier codetwin_schema.sql. Additive only: two nullable
-- columns, no data is changed or removed. Safe to run more than once.
--   heartbeat_at   last sign of life from the worker; a stale one lets the API fail the run
--                  so the teacher can retry it instead of it staying "running" for ever
--   error_message  why a run failed, in words the teacher can act on
--
-- Local SQLite databases get the same columns automatically at start-up (db.py, _migrate_sqlite).

IF COL_LENGTH('dbo.similarity_runs', 'heartbeat_at') IS NULL
    ALTER TABLE dbo.similarity_runs ADD heartbeat_at DATETIME2(0) NULL;
GO

IF COL_LENGTH('dbo.similarity_runs', 'error_message') IS NULL
    ALTER TABLE dbo.similarity_runs ADD error_message VARCHAR(500) NULL;
GO
