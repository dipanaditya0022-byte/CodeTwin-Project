import { useMemo, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import { pct, person } from "../api.js";
import { Loading, Status, useApi } from "../ui.jsx";

const COLOURS = 6;

// line number -> index of the match block that covers it
function lineMap(matches, side) {
  const map = new Map();
  matches.forEach((m, i) => {
    const [from, to] = m[side];
    for (let line = from; line <= to; line++) if (!map.has(line)) map.set(line, i);
  });
  return map;
}

function CodePane({ title, code, marks, paneRef }) {
  // code is rendered as text nodes, never as HTML
  const lines = code.split("\n");
  return (
    <div className="pane">
      <h3>{title}</h3>
      <pre ref={paneRef}>
        {lines.map((text, i) => {
          const match = marks.get(i + 1);
          return (
            <div key={i} data-line={i + 1} className={match === undefined ? "ln" : `ln hl hl-${match % COLOURS}`}>
              <span className="no">{i + 1}</span>
              <span className="tx">{text || " "}</span>
            </div>
          );
        })}
      </pre>
    </div>
  );
}

const DECISION = { pending: "Not reviewed yet", under_review: "Open for responses", cleared: "Cleared",
  confirmed: "Confirmed" };

// Why the model gave this probability: each score's push, on the log-odds scale the model adds up.
function Explanation({ e }) {
  const top = Math.max(...e.parts.map((p) => Math.abs(p.contribution)), 0.01);
  return (
    <div className="card explanation">
      <h2>Why this score</h2>
      <p>Main reason: <strong>{e.main_reason}</strong>.</p>
      <table>
        <thead><tr><th>Signal</th><th>Score</th><th>Push towards "copy"</th></tr></thead>
        <tbody>
          {e.parts.map((p) => (
            <tr key={p.feature}>
              <td>{p.label}</td><td>{pct(p.score)}</td>
              <td><span className="bar" style={{ width: `${Math.round((Math.abs(p.contribution) / top) * 100)}%` }} />
                <small className="muted"> {p.contribution.toFixed(2)}</small></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">The model adds these pushes to a starting value of {e.intercept.toFixed(2)}
        and turns the total into the probability. Model <code>{e.model_version}</code>.</p>
    </div>
  );
}

function Notes({ who, notes }) {
  if (!notes?.length) return null;
  return (
    <div className="note-care" role="note">
      <strong>Read with care: {who}</strong>
      <ul>{notes.map((n) => <li key={n.code}>{n.text}</li>)}</ul>
    </div>
  );
}

export default function Pair() {
  const { pairId } = useParams();
  const [pair, error] = useApi(`/pairs/${pairId}`);
  const left = useRef(null);
  const right = useRef(null);
  const marksA = useMemo(() => (pair ? lineMap(pair.matches, "a_lines") : new Map()), [pair]);
  const marksB = useMemo(() => (pair ? lineMap(pair.matches, "b_lines") : new Map()), [pair]);

  function jump(m) {
    for (const [ref, line] of [[left, m.a_lines[0]], [right, m.b_lines[0]]]) {
      const el = ref.current?.querySelector(`[data-line="${line}"]`);
      if (el) ref.current.scrollTop = el.offsetTop - ref.current.offsetTop - 40;
    }
  }

  return (
    <Loading data={pair} error={error}>
      {pair && (
        <section>
          <p className="crumbs">
            <Link to={`/runs/${pair.run_id}`}>Run #{pair.run_id}</Link> · {pair.assignment_title}
          </p>
          <h1>Compare submissions</h1>
          <div className="verdicts">
            <div className={`verdict ${pair.machine.flagged ? "verdict-flag" : ""}`}>
              <small>Software suspicion</small>
              <strong>{pair.machine.flagged ? "Flagged" : "Not flagged"}</strong>
              <span>{pct(pair.copy_probability)} copy probability (flag at {pct(pair.threshold)})</span>
            </div>
            <div className="verdict">
              <small>Human decision</small>
              <strong>{pair.human.decision ? DECISION[pair.human.decision] : "No review (not flagged)"}</strong>
              {pair.cluster && <Link to={`/reviews/${pair.cluster.review_id}`}>Open group #{pair.cluster.cluster_no}</Link>}
            </div>
          </div>
          <dl className="facts">
            <div><dt>Shared fragments</dt><dd>{pct(pair.fingerprint_score)}</dd></div>
            {pair.containment_score != null && (
              <div><dt>Smaller file found in the other</dt><dd>{pct(pair.containment_score)}</dd></div>
            )}
            <div><dt>Similar structure</dt><dd>{pct(pair.embedding_score)}</dd></div>
            <div><dt>Model</dt><dd><code>{pair.model_version}</code></dd></div>
          </dl>
          <p className="muted">
            A flag is evidence for your decision, not a verdict: honest solutions to short exercises can look alike.
            Highlighted blocks have the same structure after names, values and comments are ignored.
          </p>
          <Notes who={`A · ${person(pair.student_a_roll_no, pair.student_a_name)}`} notes={pair.notes_a} />
          <Notes who={`B · ${person(pair.student_b_roll_no, pair.student_b_name)}`} notes={pair.notes_b} />
          {pair.explanation && <Explanation e={pair.explanation} />}
          {pair.matches.length > 0 ? (
            <div className="legend">
              {pair.matches.map((m, i) => (
                <button key={i} className={`chip hl-${i % COLOURS}`} onClick={() => jump(m)}>
                  A {m.a_lines[0]}–{m.a_lines[1]} ↔ B {m.b_lines[0]}–{m.b_lines[1]} · {m.tokens} tokens
                </button>
              ))}
            </div>
          ) : <p className="muted">No matching blocks long enough to highlight.</p>}
          <div className="compare">
            <CodePane title={`A · ${person(pair.student_a_roll_no, pair.student_a_name)}`} code={pair.code_a} marks={marksA} paneRef={left} />
            <CodePane title={`B · ${person(pair.student_b_roll_no, pair.student_b_name)}`} code={pair.code_b} marks={marksB} paneRef={right} />
          </div>
        </section>
      )}
    </Loading>
  );
}
