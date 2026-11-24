-- Migration 004: submission forms (Azure SQL)
--
-- Additive: one new table and three nullable columns on dbo.submissions. No row is changed.
-- Safe to run more than once.

SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF OBJECT_ID('dbo.submission_forms') IS NULL
    CREATE TABLE dbo.submission_forms (
        form_id         INT IDENTITY(1,1) NOT NULL,
        assignment_id   INT               NOT NULL,
        public_token    VARCHAR(64)       NOT NULL,
        instructions    NVARCHAR(2000)    NULL,
        fields_json     NVARCHAR(MAX)     NOT NULL,   -- [{"key", "label", "kind", "required"}, ...]
        identity_field  VARCHAR(30)       NOT NULL,   -- the field that says who a submission belongs to
        is_open         BIT               NOT NULL CONSTRAINT DF_forms_is_open        DEFAULT (1),
        closes_at       DATETIME2(0)      NULL,
        allow_resubmit  BIT               NOT NULL CONSTRAINT DF_forms_allow_resubmit DEFAULT (1),
        created_at      DATETIME2(0)      NOT NULL CONSTRAINT DF_forms_created_at     DEFAULT (SYSUTCDATETIME()),
        updated_at      DATETIME2(0)      NOT NULL CONSTRAINT DF_forms_updated_at     DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_submission_forms         PRIMARY KEY (form_id),
        CONSTRAINT FK_forms_assignment         FOREIGN KEY (assignment_id) REFERENCES dbo.assignments (assignment_id),
        CONSTRAINT UQ_forms_assignment         UNIQUE (assignment_id),
        CONSTRAINT UQ_forms_token              UNIQUE (public_token),
        CONSTRAINT CK_forms_fields_json        CHECK (ISJSON(fields_json) = 1)
    );;

IF COL_LENGTH('dbo.submissions', 'source') IS NULL
    ALTER TABLE dbo.submissions ADD source VARCHAR(10) NULL
        CONSTRAINT CK_submissions_source CHECK (source IN ('upload', 'single', 'form', 'import'));
IF COL_LENGTH('dbo.submissions', 'answers_json') IS NULL
    ALTER TABLE dbo.submissions ADD answers_json NVARCHAR(MAX) NULL;
IF COL_LENGTH('dbo.submissions', 'receipt_hash') IS NULL
    ALTER TABLE dbo.submissions ADD receipt_hash CHAR(64) NULL;

COMMIT TRANSACTION;
GO
