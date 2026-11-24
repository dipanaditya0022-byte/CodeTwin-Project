-- Migration 003: course codes unique per owner (SQLite). Run by db.py at start-up.
--
-- Course codes were unique across the whole platform, so one customer's "CS101" blocked
-- another's, and the error revealed that the other course existed. They are now unique per
-- owner. Rows are copied unchanged; the table is rebuilt because SQLite cannot drop a
-- constraint in place. Statements are separated by a semicolon at the end of a line.

CREATE TABLE courses_new (
    course_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id   INTEGER       NOT NULL REFERENCES users (user_id),
    course_code  VARCHAR(20)   NOT NULL,
    course_name  NVARCHAR(120) NOT NULL,
    semester     VARCHAR(20)   NOT NULL,
    UNIQUE (teacher_id, course_code, semester)
);

INSERT INTO courses_new (course_id, teacher_id, course_code, course_name, semester)
SELECT course_id, teacher_id, course_code, course_name, semester FROM courses;

DROP TABLE courses;
ALTER TABLE courses_new RENAME TO courses;

CREATE INDEX IX_courses_teacher ON courses (teacher_id);
