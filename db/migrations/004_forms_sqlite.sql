-- Migration 004: submission forms (SQLite). Run by db.py at start-up, in one transaction.
--
-- Additive: one new table and three nullable columns on submissions. No row is changed.
-- Statements are separated by a semicolon at the end of a line.

-- A public submission form for one assignment, reached through an unguessable link
CREATE TABLE submission_forms (
    form_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id   INTEGER        NOT NULL UNIQUE REFERENCES assignments (assignment_id),
    public_token    VARCHAR(64)    NOT NULL UNIQUE,
    instructions    NVARCHAR(2000) NULL,
    fields_json     TEXT           NOT NULL,   -- [{"key", "label", "kind", "required"}, ...]
    identity_field  VARCHAR(30)    NOT NULL,   -- the field that says who a submission belongs to
    is_open         INTEGER        NOT NULL DEFAULT 1 CHECK (is_open IN (0, 1)),
    closes_at       TEXT           NULL,
    allow_resubmit  INTEGER        NOT NULL DEFAULT 1 CHECK (allow_resubmit IN (0, 1)),
    created_at      TEXT           NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    updated_at      TEXT           NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

ALTER TABLE submissions ADD COLUMN source VARCHAR(10) NULL CHECK (source IN ('upload', 'single', 'form', 'import'));

ALTER TABLE submissions ADD COLUMN answers_json TEXT NULL;

ALTER TABLE submissions ADD COLUMN receipt_hash CHAR(64) NULL;
