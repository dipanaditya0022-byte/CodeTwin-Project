import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, download, pct, when, person } from "../api.js";
import { Empty, ErrorNote, Loading, Status, useApi } from "../ui.jsx";

export default function Run() {
  const { runId } = useParams();
  const [run, error, reload] = useApi(`/runs/${runId}`);
  const [minScore, setMinScore] = useState(0.5);
  const [tab, setTab] = useState("clusters");
  const done = run?.status === "completed";
  const [pairs, pairsError] = useApi(done ? `/runs/${runId}/pairs?min_probability=${minScore}&limit=500` : null);
  const [clusters, clustersError] = useApi(done ? `/runs/${runId}/clusters` : null);
  const [retryError, setRetryError] = useState(null);

  // the run executes in the background worker, so poll until it finishes
  useEffect(() => {
    if (!run || done || run.status === "failed") return;
    const t = setTimeout(reload, 2000);
    return () => clearTimeout(t);
  }, [run, done, reload]);

  async function retry() {
    try {
      await api(`/runs/${runId}/retry`, { method: "POST" });
      reload();
    } catch (err) {
      setRetryError(err);
    }
  }

  return (
    <Loading data={run} error={error}>
      {run && (
        <section>
          <p className="crumbs">
            <Link to="/courses">My courses</Link> / <Link to={`/courses/${run.course_id}`}>Course</Link> /{" "}
            <Link to={`/assignments/${run.assignment_id}`}>{run.assignment_title}</Link>
          </p>
          <h1>Run #{run.run_id} <Status value={run.status} /></h1>
          <dl className="facts">
            <div><dt>Started</dt><dd>{when(run.started_at)}</dd></div>
            <div><dt>Finished</dt><dd>{when(run.finished_at)}</dd></div>
            <div><dt>Pairs scored</dt><dd>{run.pair_count}</dd></div>
            <div><dt>Flagged</dt><dd>{run.flagged_count}</dd></div>
            <div><dt>Clusters</dt><dd>{run.cluster_count}</dd></div>
            <div><dt>Threshold</dt><dd>{run.threshold}</dd></div>
            <div><dt>Model</dt><dd><code>{run.model_version}</code></dd></div>
          </dl>
          {run.threshold_meaning && (
            <p className="muted small">
              On the labelled test set (synthetic copies), a threshold of {run.threshold_meaning.threshold} caught{" "}
              {pct(run.threshold_meaning.recall)} of copies and {pct(run.threshold_meaning.partial_recall)} of partial
              copies, with {run.threshold_meaning.false_positives_per_1000_honest_pairs} false flags per 1,000 honest
              pairs. Real submissions may differ.
            </p>
          )}
          {done && (
            <p className="downloads">
              <button onClick={() => download(`/runs/${run.run_id}/report.html`, `codetwin-run-${run.run_id}.html`)}>
                Download report (HTML, prints to PDF)</button>
              <button onClick={() => download(`/runs/${run.run_id}/report.csv`, `codetwin-run-${run.run_id}.csv`)}>
                Download all pairs (CSV)</button>
            </p>
          )}
          {done && run.file_notes?.length > 0 && (
            <details className="card note-care">
              <summary><strong>{run.file_notes.length} file{run.file_notes.length === 1 ? "" : "s"} to read with care</strong>
                {" "}— their scores are less reliable</summary>
              <ul>
                {run.file_notes.map((f) => (
                  <li key={f.submission_id}>{person(f.roll_no, f.full_name)}: {f.notes.map((n) => n.text).join(" ")}</li>
                ))}
              </ul>
            </details>
          )}
          {(run.status === "queued" || run.status === "running") && <p className="muted">Working… this page refreshes itself.</p>}
          {run.status === "failed" && (
            <div className="run-failed" role="alert">
              <p><strong>The run failed and saved nothing.</strong></p>
              {run.error_message && <p>{run.error_message}</p>}
              <p><button onClick={retry}>Retry</button> <ErrorNote error={retryError} /></p>
            </div>
          )}
          {done && (
            <>
              <div className="tabs">
                <button className={tab === "clusters" ? "active" : ""} onClick={() => setTab("clusters")}>Clusters to review</button>
                <button className={tab === "pairs" ? "active" : ""} onClick={() => setTab("pairs")}>Ranked pairs</button>
              </div>
              {tab === "clusters" && (
                <Loading data={clusters} error={clustersError}>
                  {clusters?.length === 0 ? <Empty>No pair reached the threshold. Nothing to review.</Empty> : (
                    <table>
                      <thead><tr><th>Cluster</th><th>Students</th><th>Highest probability</th><th>Decision</th><th>Responses</th><th /></tr></thead>
                      <tbody>
                        {clusters?.map((c) => (
                          <tr key={c.cluster_id}>
                            <td>#{c.cluster_no}</td>
                            <td>{c.members.map((m) => person(m.roll_no, m.full_name)).join(", ")}</td>
                            <td>{pct(c.max_probability)}</td><td><Status value={c.decision} /></td>
                            <td>{c.response_count}</td>
                            <td><Link to={`/reviews/${c.review_id}`}>Review</Link></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </Loading>
              )}
              {tab === "pairs" && (
                <>
                  <div className="toolbar">
                    <label>
                      Minimum copy probability: <strong>{pct(minScore)}</strong>
                      <input type="range" min="0" max="1" step="0.05" value={minScore}
                             onChange={(e) => setMinScore(Number(e.target.value))} />
                    </label>
                    <span className="muted">{pairs ? `${pairs.total} of ${run.pair_count} pairs` : ""}</span>
                  </div>
                  <Loading data={pairs} error={pairsError}>
                    <table>
                      <thead><tr><th>Student A</th><th>Student B</th><th>Fingerprint</th><th>Embedding</th><th>Copy probability</th><th /></tr></thead>
                      <tbody>
                        {pairs?.items.map((p) => (
                          <tr key={p.pair_id} className={p.flagged ? "flagged" : ""}>
                            <td>{person(p.student_a_roll_no, p.student_a_name)}</td>
                            <td>{person(p.student_b_roll_no, p.student_b_name)}</td>
                            <td>{pct(p.fingerprint_score)}</td><td>{pct(p.embedding_score)}</td>
                            <td><Meter value={p.copy_probability} /></td>
                            <td><Link to={`/pairs/${p.pair_id}`}>Compare</Link></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </Loading>
                </>
              )}
            </>
          )}
        </section>
      )}
    </Loading>
  );
}

function Meter({ value }) {
  return (
    <span className="meter" title={pct(value)}>
      <span style={{ width: `${Number(value) * 100}%` }} />
      <em>{pct(value)}</em>
    </span>
  );
}
