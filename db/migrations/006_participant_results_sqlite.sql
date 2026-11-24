-- Migration 006: participant results and responses (SQLite). Run by db.py at start-up, in one transaction.
--
-- * responses can come from a participant (someone without an account) as well as a student account:
--   the table is rebuilt so student_id can be empty, with participant_id beside it. Rows are copied unchanged.
-- * submission_forms.result_visibility: what a submitter sees with their receipt code
-- * an index on submissions.receipt_hash, used to find a submission from a receipt code
-- Statements are separated by a semicolon at the end of a line.

CREATE TABLE responses_new (
    response_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id           INTEGER        NOT NULL REFERENCES reviews (review_id),
    student_id          INTEGER        NULL REFERENCES users (user_id),
    participant_id      INTEGER        NULL REFERENCES participants (participant_id),
    response_text       NVARCHAR(2000) NOT NULL,
    evidence_blob_path  VARCHAR(400)   NULL,
    created_at          TEXT           NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    CHECK ((student_id IS NULL) <> (participant_id IS NULL)),   -- from a student account or a participant
    UNIQUE (review_id, student_id),
    UNIQUE (review_id, participant_id)
);

INSERT INTO responses_new (response_id, review_id, student_id, participant_id, response_text, evidence_blob_path,
                           created_at)
SELECT response_id, review_id, student_id, NULL, response_text, evidence_blob_path, created_at FROM responses;

DROP TABLE responses;

ALTER TABLE responses_new RENAME TO responses;

CREATE INDEX IX_responses_student ON responses (student_id);

CREATE INDEX IX_responses_participant ON responses (participant_id);

CREATE INDEX IX_submissions_receipt ON submissions (receipt_hash);

ALTER TABLE submission_forms ADD COLUMN result_visibility VARCHAR(10) NOT NULL DEFAULT 'status'
    CHECK (result_visibility IN ('none', 'status', 'matches'));
