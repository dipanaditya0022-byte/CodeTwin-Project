import { useMemo, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import { pct } from "../api.js";
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
          <dl className="facts">
            <div><dt>Copy probability</dt><dd className="big">{pct(pair.copy_probability)}</dd></div>
            <div><dt>Fingerprint score</dt><dd>{pct(pair.fingerprint_score)}</dd></div>
            <div><dt>Embedding score</dt><dd>{pct(pair.embedding_score)}</dd></div>
            <div><dt>Threshold</dt><dd>{pct(pair.threshold)}</dd></div>
            <div><dt>Model</dt><dd><code>{pair.model_version}</code></dd></div>
            {pair.cluster && (
              <div><dt>Review</dt><dd><Link to={`/reviews/${pair.cluster.review_id}`}>Cluster #{pair.cluster.cluster_no}</Link> <Status value={pair.cluster.decision} /></dd></div>
            )}
          </dl>
          <p className="muted">
            The probability is evidence for your decision, not a verdict. Highlighted blocks have the same
            token structure after names and literals are ignored.
          </p>
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
            <CodePane title={`A · ${pair.student_a_roll_no} ${pair.student_a_name}`} code={pair.code_a} marks={marksA} paneRef={left} />
            <CodePane title={`B · ${pair.student_b_roll_no} ${pair.student_b_name}`} code={pair.code_b} marks={marksB} paneRef={right} />
          </div>
        </section>
      )}
    </Loading>
  );
}
