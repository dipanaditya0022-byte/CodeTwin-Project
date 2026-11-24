-- Migration 003: course codes unique per owner (Azure SQL)
--
-- Course codes were unique across the whole platform, so one customer's "CS101" blocked another's,
-- and the error revealed that the other course existed. They are now unique per owner. No data
-- changes: one unique constraint is replaced by a wider one. Safe to run more than once.

-- Filtered indexes, computed columns and views need these settings; sqlcmd defaults QUOTED_IDENTIFIER to OFF.
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_courses_code_sem')
    ALTER TABLE dbo.courses DROP CONSTRAINT UQ_courses_code_sem;
IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_courses_owner_code_sem')
    ALTER TABLE dbo.courses ADD CONSTRAINT UQ_courses_owner_code_sem UNIQUE (teacher_id, course_code, semester);

COMMIT TRANSACTION;
GO
