-- Migration 005: containment score (Azure SQL)
--
-- Adds a third similarity score to each pair: the share of the smaller file's fingerprints that
-- also occur in the other file. It catches a copied block inside a larger file, which the Jaccard
-- fingerprint score dilutes. Nullable: runs scored by two-score models leave it empty.
-- The save procedure is replaced so it stores the new score. Safe to run more than once.

-- Filtered indexes, computed columns and views need these settings; sqlcmd defaults QUOTED_IDENTIFIER to OFF.
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF COL_LENGTH('dbo.similarity_pairs', 'containment_score') IS NULL
    ALTER TABLE dbo.similarity_pairs ADD containment_score DECIMAL(5,4) NULL
        CONSTRAINT CK_pairs_containment CHECK (containment_score BETWEEN 0 AND 1);
GO

CREATE OR ALTER PROCEDURE dbo.usp_save_run_results
    @run_id    INT,
    @pairs     NVARCHAR(MAX),
    @clusters  NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF NOT EXISTS (SELECT 1 FROM dbo.similarity_runs WHERE run_id = @run_id AND status = 'running')
    BEGIN
        ;THROW 50001, 'Run not found, or it is not in the running state.', 1;
    END

    BEGIN TRY
        BEGIN TRANSACTION;

        INSERT INTO dbo.similarity_pairs
            (run_id, submission_a_id, submission_b_id, fingerprint_score, embedding_score, copy_probability,
             report_doc_id, containment_score)
        SELECT @run_id, j.a, j.b, j.fp, j.emb, j.p, j.doc, j.cont
        FROM OPENJSON(@pairs)
             WITH (a    INT           '$.a',
                   b    INT           '$.b',
                   fp   DECIMAL(5,4)  '$.fp',
                   emb  DECIMAL(5,4)  '$.emb',
                   p    DECIMAL(5,4)  '$.p',
                   doc  VARCHAR(64)   '$.doc',
                   cont DECIMAL(5,4)  '$.cont') AS j;   -- NULL for models with two scores (migration 005)

        INSERT INTO dbo.clusters (run_id, cluster_no)
        SELECT @run_id, j.cluster_no
        FROM OPENJSON(@clusters)
             WITH (cluster_no INT '$.cluster_no') AS j;

        INSERT INTO dbo.cluster_members (cluster_id, submission_id)
        SELECT c.cluster_id, CAST(m.[value] AS INT)
        FROM OPENJSON(@clusters)
             WITH (cluster_no  INT            '$.cluster_no',
                   members     NVARCHAR(MAX)  '$.members' AS JSON) AS j
        CROSS APPLY OPENJSON(j.members) AS m
        JOIN dbo.clusters AS c
          ON c.run_id = @run_id
         AND c.cluster_no = j.cluster_no;

        -- every cluster starts with one pending review
        INSERT INTO dbo.reviews (cluster_id)
        SELECT cluster_id
        FROM dbo.clusters
        WHERE run_id = @run_id;

        UPDATE dbo.similarity_runs
        SET status = 'completed',
            finished_at = SYSUTCDATETIME()
        WHERE run_id = @run_id;

        INSERT INTO dbo.audit_log (actor_id, action, entity, entity_id, old_value, new_value)
        SELECT started_by, 'run_completed', 'similarity_runs', run_id, 'running', 'completed'
        FROM dbo.similarity_runs
        WHERE run_id = @run_id;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO
