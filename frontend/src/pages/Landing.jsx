import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { SiteFooter, SiteHeader } from "../site.jsx";

const SAMPLE_A = `def binary_search(items, target):
    low, high = 0, len(items) - 1
    while low <= high:
        mid = (low + high) // 2
        if items[mid] == target:
            return mid
        elif items[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1


numbers = [int(x) for x in input().split()]
key = int(input())
print("Found at", binary_search(sorted(numbers), key))
`;

// The same program with every name changed and a comment added: what a renamed copy looks like.
const SAMPLE_B = `# search the list for the value
def find_pos(arr, value):
    left, right = 0, len(arr) - 1
    while left <= right:
        centre = (left + right) // 2
        if arr[centre] == value:
            return centre
        elif arr[centre] < value:
            left = centre + 1
        else:
            right = centre - 1
    return -1


data = [int(v) for v in input().split()]
wanted = int(input())
print("Found at", find_pos(sorted(data), wanted))
`;

// Same logic as A, rewritten: nested if/else, a main() function and new names.
const SAMPLE_RESTRUCTURED = `def find(values, wanted):
    lo = 0
    hi = len(values) - 1
    while lo <= hi:
        m = (lo + hi) // 2
        if values[m] != wanted:
            if values[m] < wanted:
                lo = m + 1
            else:
                hi = m - 1
        else:
            return m
    return -1


def main():
    nums = sorted(int(t) for t in input().split())
    k = int(input())
    print("Found at", find(nums, k))


main()
`;

// An honest, independent solution to the same problem (recursive), from the labelled set.
const SAMPLE_INDEPENDENT = `def search(seq, item, lo=0, hi=None):
    if hi is None:
        hi = len(seq)
    if lo >= hi:
        return None
    middle = lo + (hi - lo) // 2
    if seq[middle] == item:
        return middle
    if seq[middle] > item:
        return search(seq, item, lo, middle)
    return search(seq, item, middle + 1, hi)


data = [3, 8, 15, 23, 42, 57, 91]
for probe in (23, 4, 91):
    where = search(data, probe)
    print(probe, "->", "missing" if where is None else where)
`;

const SAMPLES = [
  ["Renamed copy", "Same program, every name changed and a comment added", SAMPLE_B],
  ["Restructured copy", "Same logic, rewritten with nested ifs and a main()", SAMPLE_RESTRUCTURED],
  ["Independent solution", "A different, honest solution to the same problem", SAMPLE_INDEPENDENT],
];

const MAX_CHARS = 20000;

// A probability is never shown as 0% or 100%: it is evidence, not certainty.
const probText = (v) => `${Math.min(99.9, Math.max(0.1, v * 100)).toFixed(1)}%`;

function explain(r) {
  if (r.fingerprint_score >= 0.9) return "Identical structure once names, comments and layout are ignored.";
  if (r.fingerprint_score >= 0.3) return "Large blocks of shared code, partly rewritten.";
  if (r.embedding_score >= 0.65) return "A similar overall shape but little shared code, typical of honest solutions to the same problem.";
  return "The two files have little in common.";
}
const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/* ------------------------------------------------------------------ icons */

const PATHS = {
  compare: "M4 5h7v14H4zM13 5h7v14h-7zM6 9h3M6 13h3M15 9h3M15 13h3",
  cluster: "M8 11a3 3 0 100-6 3 3 0 000 6zm8 0a3 3 0 100-6 3 3 0 000 6zm-4 8a3 3 0 100-6 3 3 0 000 6z",
  review: "M12 3v18M5 7h14M5 7l-3 7h6l-3-7zm14 0l-3 7h6l-3-7zM8 21h8",
  audit: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3zm-3 9l2 2 4-4",
  repeat: "M17 2l4 4-4 4M3 11V9a3 3 0 013-3h15M7 22l-4-4 4-4M21 13v2a3 3 0 01-3 3H3",
  starter: "M4 4h10l6 6v10H4zM14 4v6h6",
  paste: "M9 4h6v3H9zM7 5H5v16h14V5h-2M8 12h8M8 16h5",
  upload: "M12 16V4M7 9l5-5 5 5M4 17v3h16v-3",
  spark: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z",
  scan: "M3 7V4h3M18 4h3v3M21 17v3h-3M6 20H3v-3M7 12h10",
  check: "M5 12l4 4 10-10",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z",
  bulb: "M9 18h6M10 21h4M12 3a6 6 0 00-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0012 3z",
  cap: "M2 9l10-5 10 5-10 5-10-5zm4 2v5c0 1.5 3 3 6 3s6-1.5 6-3v-5",
  doc: "M6 3h9l5 5v13H6zM14 3v6h6M9 13h8M9 17h6",
  users: "M9 11a4 4 0 100-8 4 4 0 000 8zM2 21c0-4 3-6 7-6s7 2 7 6M17 11a3 3 0 100-6M22 21c0-3-2-5-5-5.5",
  lock: "M6 11h12v10H6zM8 11V8a4 4 0 018 0v3",
  cloud: "M7 18h10a4 4 0 00.5-8 6 6 0 00-11.5 1.5A3.5 3.5 0 007 18z",
  github: "M9 19c-4 1.5-4-2-6-2.5M15 21v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 00-1.3-3.2 4.3 4.3 0 00-.1-3.2s-1-.3-3.4 1.3a11.6 11.6 0 00-6.2 0C6.6 2.8 5.6 3.1 5.6 3.1a4.3 4.3 0 00-.1 3.2A4.6 4.6 0 004.2 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21",
  arrow: "M5 12h14M13 6l6 6-6 6",
  wand: "M4 20L16 8M14 6l4 4M18 3v3M21 6h-3M7 4v2M8 5H6",
  hash: "M5 9h14M5 15h14M10 4L8 20M16 4l-2 16",
  vector: "M4 20L20 4M20 4h-6M20 4v6M4 14v6h6",
  layers: "M12 3l9 5-9 5-9-5 9-5zm-9 9l9 5 9-5",
  eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zm10 3a3 3 0 100-6 3 3 0 000 6z",
};

function Icon({ name, size = 20 }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8"
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}

/* ------------------------------------------------------------------ motion helpers */

// Fade sections in as they scroll into view; everything is visible straight away with reduced motion.
function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window) || reducedMotion()) {
      els.forEach((el) => el.classList.add("in"));
      return undefined;
    }
    const io = new IntersectionObserver((entries) => entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("in");
        io.unobserve(entry.target);
      }
    }), { rootMargin: "0px 0px -6% 0px" });
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
}

function CountUp({ to, decimals = 0, suffix = "" }) {
  const ref = useRef(null);
  const [value, setValue] = useState(reducedMotion() ? to : 0);
  useEffect(() => {
    if (reducedMotion() || !("IntersectionObserver" in window)) return undefined;
    let frame;
    const io = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      io.disconnect();
      const start = performance.now();
      const tick = (now) => {
        const t = Math.min(1, (now - start) / 1300);
        setValue(to * (1 - Math.pow(1 - t, 3)));
        if (t < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    });
    io.observe(ref.current);
    return () => { io.disconnect(); cancelAnimationFrame(frame); };
  }, [to]);
  return <span ref={ref}>{value.toFixed(decimals)}{suffix}</span>;
}

function SectionHead({ eyebrow, title, sub }) {
  return (
    <div className="sec-head reveal">
      <span className="eyebrow">{eyebrow}</span>
      <h2 className="sec-title">{title}</h2>
      {sub && <p className="sec-sub">{sub}</p>}
    </div>
  );
}

/* ------------------------------------------------------------------ demo */

function likelihood(v) {
  if (v == null) return null;
  if (v >= 0.6) return ["High", "tag-red"];
  if (v >= 0.3) return ["Medium", "tag-amber"];
  return ["Low", "tag-green"];
}

function Gauge({ value }) {
  const tone = value == null ? "" : value >= 0.5 ? "g-red" : value >= 0.25 ? "g-amber" : "g-green";
  return (
    <div className={`semi-gauge ${tone}`}>
      <svg viewBox="0 0 120 70" aria-hidden="true">
        <defs>
          <linearGradient id="gauge-grad" x1="0" x2="1">
            <stop offset="0" stopColor="#2f7d4f" />
            <stop offset="0.5" stopColor="#b7791f" />
            <stop offset="1" stopColor="#c0392b" />
          </linearGradient>
        </defs>
        <path d="M10 62 A50 50 0 0 1 110 62" className="semi-track" pathLength="100" />
        {value != null && (
          <path d="M10 62 A50 50 0 0 1 110 62" className="semi-fill" pathLength="100"
                strokeDasharray={`${value * 100} 100`} />
        )}
      </svg>
      <strong>{value == null ? "–%" : probText(value)}</strong>
    </div>
  );
}

function EngineRow({ icon, name, value, note, prob = false }) {
  const tag = likelihood(value);
  return (
    <div className="engine-row">
      <span className="engine-icon"><Icon name={icon} size={17} /></span>
      <span className="engine-name">{name}<small>{note}</small></span>
      <span className="engine-meter"><i style={{ width: `${(value ?? 0) * 100}%` }} /></span>
      <span className="engine-value">{value == null ? "–" : prob ? probText(value) : `${Math.round(value * 100)}%`}</span>
      {tag ? <span className={`tag ${tag[1]}`}>{tag[0]}</span> : <span className="tag tag-idle">–</span>}
    </div>
  );
}

const TABS = [["compare", "Compare", "#demo"], ["cluster", "Clusters", "#features"], ["review", "Review", "#features"], ["audit", "Audit", "#different"]];

function Demo() {
  const [codes, setCodes] = useState({ a: "", b: "" });
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [sample, setSample] = useState(null);     // index into SAMPLES while a sample is loaded unchanged
  const [menuOpen, setMenuOpen] = useState(false);
  const fileInput = useRef(null);
  const uploadTarget = useRef("a");

  const set = (key, value) => {
    setCodes((c) => ({ ...c, [key]: value }));
    setResult(null);
    setSample(null);
  };

  function loadSample(i) {
    setCodes({ a: SAMPLE_A, b: SAMPLES[i][2] });
    setSample(i);
    setResult(null);
    setError(null);
    setMenuOpen(false);
  }

  useEffect(() => {
    if (!menuOpen) return undefined;
    const close = (e) => { if (!e.target.closest?.(".sample-menu")) setMenuOpen(false); };
    const esc = (e) => { if (e.key === "Escape") setMenuOpen(false); };
    document.addEventListener("click", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("click", close); document.removeEventListener("keydown", esc); };
  }, [menuOpen]);
  const emptySide = () => (codes.a.trim() ? "b" : "a");

  async function paste() {
    try {
      set(emptySide(), (await navigator.clipboard.readText()).slice(0, MAX_CHARS));
    } catch {
      setError("Your browser blocked clipboard access. Paste with Ctrl+V / Cmd+V instead.");
    }
  }

  function upload(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!file.name.endsWith(".py")) return setError("Upload a .py file");
    file.text().then((text) => set(uploadTarget.current, text.slice(0, MAX_CHARS)));
  }

  const ready = codes.a.trim() && codes.b.trim() && codes.a.length <= MAX_CHARS && codes.b.length <= MAX_CHARS;

  async function check() {
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    try {
      const [res] = await Promise.all([
        api("/demo/compare", { method: "POST", json: { code_a: codes.a, code_b: codes.b } }),
        new Promise((r) => setTimeout(r, reducedMotion() ? 0 : 700)),   // let the scan animation play once
      ]);
      setResult(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const onKey = (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      check();
    }
  };

  const lines = (s) => (s.trim() ? s.trimEnd().split("\n").length : 0);
  const p = result?.copy_probability;

  return (
    <div className="tool-frame reveal" id="demo">
      <div className="tool">
        <div className="tool-bar">
          <span className="dots"><i /><i /><i /></span>
          <nav className="tool-tabs" aria-label="CodeTwin features">
            {TABS.map(([icon, label, href], i) => (
              <a key={label} href={href} className={i === 0 ? "active" : ""}><Icon name={icon} size={16} />{label}</a>
            ))}
          </nav>
          <span className="tool-model">{result ? result.model_version : "⌘/Ctrl + Enter to run"}</span>
        </div>

        <div className="tool-body">
          <div className="tool-input">
            <div className="chip-row">
              <button type="button" className="chip" onClick={paste}><Icon name="paste" size={16} />Paste</button>
              <button type="button" className="chip" onClick={() => { uploadTarget.current = emptySide(); fileInput.current.click(); }}>
                <Icon name="upload" size={16} />Upload .py
              </button>
              <div className="sample-menu">
                <button type="button" className="chip chip-accent" aria-haspopup="menu" aria-expanded={menuOpen}
                        onClick={() => setMenuOpen(!menuOpen)}>
                  <Icon name="spark" size={16} />Try a sample<span className="caret">▾</span>
                </button>
                {menuOpen && (
                  <div className="menu" role="menu">
                    {SAMPLES.map(([title, note], i) => (
                      <button key={title} type="button" role="menuitem" onClick={() => loadSample(i)}>
                        <b>{title}</b><small>{note}</small>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              {(codes.a || codes.b) && (
                <button type="button" className="chip chip-quiet" onClick={() => { setCodes({ a: "", b: "" }); setResult(null); setError(null); setSample(null); }}>
                  Clear
                </button>
              )}
              <input ref={fileInput} type="file" accept=".py" hidden onChange={upload} />
            </div>
            {sample != null && (
              <p className="sample-note"><b>Sample: {SAMPLES[sample][0]}.</b> {SAMPLES[sample][1]}. Press Check similarity.</p>
            )}
            <div className={`editors${busy ? " scanning" : ""}`}>
              {[["a", "submission_a.py"], ["b", "submission_b.py"]].map(([key, label]) => (
                <label key={key} className="editor">
                  <span className="editor-tab"><i className={`file-dot ${key}`} />{label}<small>{lines(codes[key])} lines</small></span>
                  <textarea value={codes[key]} spellCheck="false" placeholder="Paste Python code here…"
                            onChange={(e) => set(key, e.target.value)} onKeyDown={onKey} />
                </label>
              ))}
            </div>
            <div className="tool-footer">
              <span className="muted-count"><Icon name="shield" size={15} />Nothing you paste is stored</span>
              <button type="button" className="scan-btn" disabled={!ready || busy} onClick={check}>
                <Icon name="scan" size={18} />{busy ? "Scanning…" : "Check similarity"}
              </button>
            </div>
          </div>

          <div className="tool-report" aria-live="polite">
            <div className="report-card">
              <span className="report-label">Copy probability</span>
              <Gauge value={p} />
              {result
                ? <span className={`verdict ${result.flagged ? "v-flag" : "v-ok"}`}>{result.flagged ? "Would be flagged for review" : "Looks independent"}</span>
                : <span className="verdict v-idle">{error || "Run a check to see the report"}</span>}
              {result && <span className="verdict-why">{explain(result)}</span>}
              {result?.notes && Object.keys(result.notes).length > 0 && (
                <span className="verdict-why demo-care" role="note">
                  <b>Read with care:</b> {[...new Set(Object.values(result.notes).flat())].join(" ")}
                </span>
              )}
            </div>
            <p className="report-sub">Signals</p>
            <EngineRow icon="hash" name="Fingerprint" note="winnowed k-grams" value={result?.fingerprint_score} />
            <EngineRow icon="vector" name="Structure" note="code embedding" value={result?.embedding_score} />
            <EngineRow icon="spark" name="Classifier" note="weighs both" value={p} prob />
            {result?.matches?.length > 0 && (
              <div className="match-list">
                {result.matches.slice(0, 3).map((m, i) => (
                  <span key={i}>A {m.a_lines[0]}–{m.a_lines[1]} <Icon name="arrow" size={13} /> B {m.b_lines[0]}–{m.b_lines[1]} <em>{m.tokens} tokens</em></span>
                ))}
              </div>
            )}
            <p className="report-note">Evidence for a teacher's review, never a verdict on its own.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ pipeline */

const PIPELINE = [
  ["wand", "Normalise", "Names and literals become placeholders, comments go."],
  ["hash", "Fingerprint", "Every 5-token run is hashed; a winnowed subset is kept."],
  ["vector", "Embed", "A pretrained code model turns each file into a vector."],
  ["spark", "Classify", "A trained model weighs both scores into one probability."],
  ["cluster", "Cluster", "Flagged pairs that share a file become one case."],
  ["eye", "Explain", "Matched line ranges feed the side-by-side view."],
];

function Pipeline() {
  return (
    <section className="pipeline-sec" id="pipeline">
      <div className="site-wrap">
        <SectionHead eyebrow="Under the hood" title="How CodeTwin Reads Code"
                     sub="Six steps turn a folder of submissions into ranked, explained cases. Renaming a variable changes nothing in step one." />
        <ol className="pipeline reveal">
          {PIPELINE.map(([icon, name, text], i) => (
            <li key={name} style={{ "--i": i }}>
              <span className="node"><Icon name={icon} size={22} /></span>
              <b>{name}</b>
              <p>{text}</p>
            </li>
          ))}
        </ol>
        <div className="sees reveal">
          <div className="sees-col">
            <span className="sees-label">What the student wrote</span>
            <pre>{"total = price * qty   # final cost\nif total > budget:\n    print(\"Over budget\")"}</pre>
          </div>
          <span className="sees-arrow"><Icon name="arrow" size={22} /></span>
          <div className="sees-col">
            <span className="sees-label">What CodeTwin compares</span>
            <pre className="tokens">{"ID = ID * ID\nif ID > ID :\n    ID ( LIT )"}</pre>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ small mock-ups used as card art */

function MockCode() {
  return (
    <div className="mock-window">
      <h5><i className="file-dot b" />submission_b.py</h5>
      <pre className="mock-code">
        <span className="hl">def find_pos(arr, value):</span>{"\n"}
        <span className="hl">    left, right = 0, len(arr) - 1</span> <em className="more">+3 blocks</em>{"\n"}
        {"    while left <= right:\n        centre = (left + right) // 2\n        ...\n"}
      </pre>
      <div className="mock-foot"><span>A 1–16 ↔ B 2–17 · 117 tokens</span></div>
    </div>
  );
}

function MockReport() {
  return (
    <div className="mock-split">
      <div className="mock-window mock-rows">
        <h5>Signals</h5>
        <div className="mock-row"><Icon name="hash" size={16} />Fingerprint<span className="tag tag-red">High</span></div>
        <div className="mock-row"><Icon name="vector" size={16} />Structure<span className="tag tag-red">High</span></div>
        <div className="mock-row"><Icon name="spark" size={16} />Classifier<span className="tag tag-red">High</span></div>
      </div>
      <div className="mock-ring">
        <div className="ring"><b>99%</b><small>copy probability</small></div>
        <span className="tag tag-red">Likely copy</span>
      </div>
    </div>
  );
}

function MockReview() {
  return (
    <div className="mock-stack">
      <div className="mock-window mock-back">
        <h5>Cluster #1 <span className="tag tag-amber">Under review</span></h5>
        <p>22CS001 · 22CS002 · 22CS006</p>
      </div>
      <div className="mock-window mock-front">
        <h5>Student response <span className="tag tag-green">Received</span></h5>
        <p>“I wrote this myself during the lab session; my rough work is attached.”</p>
        <div className="mock-foot"><span>evidence.pdf</span><span className="mock-btn ghost">Clear with reason</span></div>
      </div>
    </div>
  );
}

function MockClusters() {
  return (
    <div className="mock-bubbles">
      <svg className="links" viewBox="0 0 460 300" aria-hidden="true">
        <line x1="120" y1="125" x2="240" y2="80" /><line x1="120" y1="125" x2="235" y2="200" /><line x1="240" y1="80" x2="235" y2="200" />
      </svg>
      <span className="bubble b1">22CS001</span>
      <span className="bubble b2">22CS002</span>
      <span className="bubble b3">22CS006</span>
      <span className="bubble b4">22CS010</span>
      <span className="float-tag red f1">Cluster #1 · 99.8%</span>
      <span className="float-tag green f2">Independent</span>
      <span className="float-tag violet f3">One review, not three</span>
    </div>
  );
}

function MockDemo() {
  return (
    <div className="mock-stack">
      <div className="mock-window mock-back"><h5><i className="file-dot a" />submission_a.py</h5><p>def binary_search(items, target): …</p></div>
      <div className="mock-window mock-front">
        <h5>Overall result <span className="tag tag-red">Likely copy</span></h5>
        <p>These files share 1 matched block (lines 1–16).</p>
        <div className="split-bar"><span style={{ width: "99.8%" }} /></div>
        <div className="mock-foot"><span>● 100% fingerprint</span><span>● 100% structure</span></div>
      </div>
      <span className="badge-float">FREE</span>
    </div>
  );
}

function MockTimeline() {
  return (
    <ul className="timeline">
      <li><i className="t-violet" /><b>Review opened</b><span>Prof. Kulkarni · 10:02</span></li>
      <li><i className="t-teal" /><b>Response submitted</b><span>22CS001 · 10:15 · evidence.pdf</span></li>
      <li><i className="t-green" /><b>Cleared, reason recorded</b><span>Prof. Kulkarni · 10:40</span></li>
      <li className="blocked"><i className="t-red" /><b>UPDATE audit_log</b><span>blocked by trigger · append-only</span></li>
    </ul>
  );
}

/* ------------------------------------------------------------------ content */

const WHY = [
  ["users", "Too many pairs to read", "A lab of 60 students produces 1,770 pairs of submissions. Nobody can compare that many by eye, and a renamed copy looks new."],
  ["eye", "Flags you can explain", "CodeTwin scores every pair in seconds, explains each flag line by line, and puts the matching code side by side."],
  ["review", "Decisions stay human", "Similarity is not proof. CodeTwin keeps the decision with the teacher, gives students a say first, and records every step."],
];

const USE_FOR = [
  ["cap", "Weekly lab assignments", "Upload one zip per assignment and get every pair ranked by copy probability in seconds."],
  ["starter", "Assignments with starter code", "Give students a template. Code you provide is excluded, so it never counts as a match."],
  ["users", "Large classes", "Pair count grows as n(n−1)/2. Runs happen in a background worker, so 120 files are as easy as 20."],
  ["repeat", "Repeat behaviour", "See which pairs of students are flagged together across two or more assignments of a course."],
  ["doc", "Cases that need a record", "Every decision carries a reason, a reviewer and a time, and the audit log cannot be edited."],
  ["shield", "Untrusted uploads", "Archives are size-limited, paths are sanitised, only .py files are read, and nothing is ever run."],
];

const VS_DETECTION = [
  ["What you get", "A similarity score per pair, sometimes with highlighted matches.", "A copy probability, highlighted matches, clusters and a full review workflow."],
  ["After a flag", "Handled outside the tool, by email or in person.", "The teacher opens a review, the student responds, and the decision is recorded with a reason."],
  ["Over a semester", "Each assignment is checked on its own.", "Repeat pairs across assignments and an append-only history of every decision."],
];

const VS_AI = [
  ["What it checks", "Whether two students' submissions share code, even after renaming and reordering.", "Whether a single text looks machine-written."],
  ["What it does not check", "It does not tell you if code was written by an AI tool.", "It does not find two students who copied from each other."],
];

const FAQ = [
  ["Is the demo free?", "Yes. Paste or upload two Python files and you get the full similarity report, with no account needed. Nothing you paste is stored."],
  ["How does CodeTwin detect copied code?", "It normalises each file (names and literals become placeholders), compares winnowed fingerprints of the token stream, compares code embeddings from a pretrained model, and a trained classifier turns both scores into one copy probability."],
  ["Will renaming variables or reformatting hide a copy?", "No. Renamed, reformatted, reordered and restructured copies were all caught on the labelled set, because names and layout are normalised away before comparison."],
  ["How accurate is it?", "On 885 labelled pairs with 5-fold cross-validation: precision 1.00 and recall 0.91. Partial copies, mixed with other code, are the hardest case. Accuracy on real lab submissions will be measured separately."],
  ["Does a high score prove a student copied?", "No. Short assignments have few correct solutions, so honest work can look alike. The score starts a review; the teacher reads the matched code, the student responds, and only then is a case cleared or confirmed."],
  ["Does it run the submitted code?", "Never. Code is only read as text. It is never imported or executed."],
  ["Which languages are supported?", "Python, for the lab courses CodeTwin was built for."],
  ["How is CodeTwin different from MOSS, JPlag or Dolos?", "Those tools detect similar code. CodeTwin also handles what comes after: clusters, an explained flag, a student response, a recorded decision, repeat-pair tracking and an audit trail."],
];

/* ------------------------------------------------------------------ page */

export default function Landing() {
  useReveal();
  return (
    <div className="site">
      <SiteHeader />

      <section className="hero">
        <div className="hero-bg" aria-hidden="true" />
        <div className="site-wrap">
          <a href="#pipeline" className="hero-chip"><span className="live" />Free demo · two methods + a trained classifier<Icon name="arrow" size={14} /></a>
          <h1>Catch copied code.<br /><span className="grad">Review it fairly.</span></h1>
          <p className="hero-sub">CodeTwin compares every pair of Python submissions, explains each flag line by line, and gives students a say before any decision.</p>
          <Demo />
          <div className="hero-trust">
            <span><Icon name="check" size={16} />1.00 precision · 0.91 recall</span>
            <span><Icon name="check" size={16} />No sign-up for the demo</span>
            <span><Icon name="check" size={16} />Code is never executed</span>
          </div>
        </div>
      </section>

      <Pipeline />

      <section className="sec" id="features">
        <div className="site-wrap">
          <SectionHead eyebrow="Features" title="Detect Smarter. Review Fairer."
                       sub="Detectors stop at a score. CodeTwin explains the score and runs the fair process that follows." />
          <div className="duo">
            <article className="art-card reveal">
              <div className="art"><MockCode /></div>
              <h3>See Exactly Which Lines Match</h3>
              <p>Every matched block is highlighted in both files, with line ranges and token counts, even after variables were renamed.</p>
            </article>
            <article className="art-card reveal">
              <div className="art"><MockReport /></div>
              <h3>Two Signals, One Clear Report</h3>
              <p>Fingerprint and structure scores are weighed by a trained classifier, so one weak signal never decides alone.</p>
            </article>
          </div>
          <article className="art-card wide reveal">
            <div className="art"><MockReview /></div>
            <div>
              <h3>One Review per Cluster, With the Student's Side</h3>
              <p>Copies that share a file become one case. The teacher opens it, the student responds with evidence, and the decision is recorded with a reason.</p>
            </div>
          </article>
        </div>
      </section>

      <section className="sec tint">
        <div className="site-wrap">
          <SectionHead eyebrow="The problem" title="Why Labs Need a Code Similarity Checker" />
          <div className="why-grid">
            {WHY.map(([icon, title, text]) => (
              <div key={title} className="why-card reveal">
                <span className="icon-tile"><Icon name={icon} size={22} /></span>
                <h3>{title}</h3>
                <p>{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="sec" id="how">
        <div className="site-wrap">
          <SectionHead eyebrow="Workflow" title="From Upload to Recorded Decision" />
          <div className="row-2">
            <div className="art art-tall reveal"><MockReport /></div>
            <ol className="steps reveal">
              {[["Upload", "one zip per assignment, matched to students by roll number."],
                ["Run", "a check that scores every pair in a background worker."],
                ["Review", "clusters ranked by probability, side by side."],
                ["Decide", "with a reason, after the student has responded."]].map(([b, t], i) => (
                <li key={b}><span className="step-no">{String(i + 1).padStart(2, "0")}</span><div><b>{b}</b> {t}</div></li>
              ))}
              <li className="steps-link"><a href="#demo" className="inline-link">Try it on two files now <Icon name="arrow" size={16} /></a></li>
            </ol>
          </div>
        </div>
      </section>

      <section className="sec tint" id="everything">
        <div className="site-wrap">
          <SectionHead eyebrow="Everything included" title="Everything You Need to Review Copied Code" />
          <div className="row-2 reveal">
            <div className="art art-tall">
              <div className="engine-mock">
                <div><Icon name="hash" size={18} /><b>Fingerprint</b><span>92% similar</span><em className="tag tag-red">High</em></div>
                <div><Icon name="vector" size={18} /><b>Structure</b><span>98% similar</span><em className="tag tag-red">High</em></div>
                <div><Icon name="spark" size={18} /><b>Classifier</b><span>99% copy</span><em className="tag tag-red">Flagged</em></div>
              </div>
            </div>
            <div className="feature-text">
              <h3>Two Methods, One Probability</h3>
              <p>Winnowed k-gram fingerprints (the technique behind MOSS) catch shared code. A pretrained code-embedding model catches copies that were restructured. A logistic regression, trained on a labelled set, weighs both into one copy probability, with two weights you can explain.</p>
            </div>
          </div>
          <div className="row-2 flip reveal">
            <div className="feature-text right">
              <h3>Free Similarity Demo, No Sign-Up</h3>
              <p>Paste or upload two Python files at the top of this page and get the full report from the same pipeline a real run uses. Nothing you paste is stored.</p>
            </div>
            <div className="art art-tall"><MockDemo /></div>
          </div>
          <div className="row-2 reveal">
            <div className="art art-tall"><MockClusters /></div>
            <div className="feature-text">
              <h3>Clusters Instead of Hundreds of Pairs</h3>
              <p>Three students who shared one file become one review, not three. Honest look-alikes can be cleared before any student is notified, and independent work stays out of the case.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="sec">
        <div className="site-wrap">
          <SectionHead eyebrow="Use cases" title="A Code Checker for Every Kind of Lab Work"
                       sub="Whether it is a weekly exercise or a graded project, CodeTwin helps you find work that may have been shared, and settle it fairly." />
          <div className="use-grid">
            {USE_FOR.map(([icon, title, text]) => (
              <div key={title} className="use-card reveal">
                <span className="icon-tile"><Icon name={icon} size={22} /></span>
                <h3>{title}</h3>
                <p>{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="sec tint" id="compare">
        <div className="site-wrap">
          <SectionHead eyebrow="Compare" title="CodeTwin vs Detection-Only Tools"
                       sub="Detection tools such as MOSS, JPlag and Dolos find similar code. CodeTwin adds what has to happen next." />
          <div className="cmp-table reveal">
            <div className="cmp-row cmp-head"><span /><span>Detection-only tools</span><span className="us">CodeTwin</span></div>
            {VS_DETECTION.map(([k, a, b]) => (
              <div key={k} className="cmp-row">
                <span>{k}</span><span data-label="Detection-only tools">{a}</span><span data-label="CodeTwin" className="us">{b}</span>
              </div>
            ))}
          </div>
          <div className="tip reveal"><Icon name="bulb" size={22} /><span><b>Recommended workflow:</b> run a check, clear honest look-alikes first, open a review for the rest, and decide only after the student has responded.</span></div>

          <div className="spaced">
            <SectionHead eyebrow="Not the same tool" title="Code Similarity Checker vs AI Detector"
                         sub="One finds students who share code. The other guesses whether text was machine-written." />
          </div>
          <div className="cmp-table reveal">
            <div className="cmp-row cmp-head"><span /><span className="us">Code similarity checker</span><span>AI detector</span></div>
            {VS_AI.map(([k, a, b]) => (
              <div key={k} className="cmp-row">
                <span>{k}</span><span data-label="Code similarity checker" className="us">{a}</span><span data-label="AI detector">{b}</span>
              </div>
            ))}
          </div>
          <p className="sec-foot reveal"><b>Code can be original but AI-generated. It can also be copied from a classmate without any AI.</b> CodeTwin focuses on the second.</p>
        </div>
      </section>

      <section className="sec signal">
        <div className="site-wrap narrow center reveal">
          <span className="eyebrow">Responsible use</span>
          <h2 className="sec-title">A Similarity Score Is a Signal, Not Final Proof</h2>
          <p className="lead">No checker can prove with certainty that a student copied. Scores vary with assignment length and how many correct solutions exist, and short programs are harder to judge.</p>
          <p className="lead">That is why CodeTwin never confirms a case by itself. Every flag goes to a teacher, every student can respond, and every decision carries a reason.</p>
        </div>
      </section>

      <section className="sec" id="roles">
        <div className="site-wrap">
          <SectionHead eyebrow="Roles" title="Who Uses CodeTwin?" />
          <div className="who-grid">
            {[["users", "Teachers", "Upload a lab, start a run, review clusters ranked by probability, and clear or confirm each case with a reason."],
              ["cap", "Students", "See flags on your own submissions only, respond once with evidence, and read the reason for every decision."],
              ["shield", "Administrators", "Create users, courses and enrolments, and read the full audit log of every action."],
              ["layers", "Departments", "Track repeat pairs and review turnaround across courses through reporting views."]].map(([icon, who, text]) => (
              <div key={who} className="who-card reveal">
                <span className="who-pill"><Icon name={icon} size={17} />{who}</span>
                <p>{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="sec tint" id="different">
        <div className="site-wrap">
          <SectionHead eyebrow="Why CodeTwin" title="What Makes CodeTwin Different?"
                       sub="Explained flags, a process students can trust, and a record nobody can rewrite." />
          <div className="bento">
            <div className="bento-card span-2 reveal">
              <div>
                <span className="icon-tile"><Icon name="review" size={22} /></span>
                <h3>Students respond before any decision</h3>
                <p>A case can only be confirmed after the teacher opens it, so every flagged student gets to answer first. Every step lands in the history.</p>
              </div>
              <MockTimeline />
            </div>
            <div className="bento-card reveal">
              <span className="icon-tile"><Icon name="audit" size={22} /></span>
              <h3>Tamper-proof audit trail</h3>
              <p>A database trigger logs every decision change, and a second trigger blocks any edit or delete.</p>
            </div>
            <div className="bento-card reveal">
              <span className="icon-tile"><Icon name="cluster" size={22} /></span>
              <h3>Clusters, not piles of pairs</h3>
              <p>Flagged pairs that share a submission become one case, with one review and one decision.</p>
            </div>
            <div className="bento-card reveal">
              <span className="icon-tile"><Icon name="repeat" size={22} /></span>
              <h3>Repeat-pair tracking</h3>
              <p>Students flagged together again and again stand out across the whole course.</p>
            </div>
            <div className="bento-card reveal">
              <span className="icon-tile"><Icon name="lock" size={22} /></span>
              <h3>Code is never executed</h3>
              <p>Submissions are tokenised and embedded as text only. A malicious file cannot run on the server.</p>
            </div>
            <div className="bento-card span-3 cloud-card reveal">
              <div>
                <span className="icon-tile"><Icon name="cloud" size={22} /></span>
                <h3>Student code stays in your cloud</h3>
                <p>The embedding model runs inside the worker on your Azure tenant. No code is sent to an outside AI service.</p>
              </div>
              <div className="flow-chips">
                <span>Browser</span><Icon name="arrow" size={16} /><span>FastAPI</span><Icon name="arrow" size={16} />
                <span>Queue</span><Icon name="arrow" size={16} /><span className="hot">Worker + model</span><Icon name="arrow" size={16} /><span>Azure SQL</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="sec">
        <div className="site-wrap">
          <SectionHead eyebrow="Results" title="Measured, Not Promised"
                       sub="885 labelled pairs, stratified 5-fold cross-validation, and a benchmark on a laptop CPU." />
          <div className="stat-grid">
            <div className="stat-card reveal"><b><CountUp to={1} decimals={2} /></b><span>precision</span><p>No false accusations on the labelled set</p></div>
            <div className="stat-card reveal"><b><CountUp to={0.91} decimals={2} /></b><span>recall</span><p>Every renamed, reordered and restructured copy caught</p></div>
            <div className="stat-card reveal"><b><CountUp to={3.2} decimals={1} suffix=" s" /></b><span>for 60 files</span><p>1,770 pairs scored, against a 5-minute target</p></div>
            <div className="stat-card reveal"><b><CountUp to={0} /></b><span>lines executed</span><p>Uploaded code is only ever read as text</p></div>
          </div>
        </div>
      </section>

      <section className="sec tint">
        <div className="site-wrap">
          <SectionHead eyebrow="Get started" title="Explore CodeTwin" />
          <div className="explore-grid">
            {[["users", "Teacher dashboard", "/login"], ["cap", "Create a student account", "/signup"],
              ["compare", "Try the similarity demo", "#demo"], ["layers", "See the pipeline", "#pipeline"],
              ["github", "Source code on GitHub", "https://github.com/dipanaditya0022-byte/CodeTwin-Project"]].map(([icon, label, to]) => {
              const inner = <><span className="icon-tile sm"><Icon name={icon} size={18} /></span>{label}<span className="go"><Icon name="arrow" size={16} /></span></>;
              if (to.startsWith("/")) return <Link key={label} to={to} className="explore-card reveal">{inner}</Link>;
              return <a key={label} href={to} className="explore-card reveal" {...(to.startsWith("http") ? { target: "_blank", rel: "noreferrer" } : {})}>{inner}</a>;
            })}
          </div>
        </div>
      </section>

      <section className="sec" id="faq">
        <div className="site-wrap faq-wrap">
          <SectionHead eyebrow="FAQ" title="Questions, Answered" />
          {FAQ.map(([q, a]) => (
            <details key={q} className="reveal">
              <summary>{q}</summary>
              <p>{a}</p>
            </details>
          ))}
        </div>
      </section>

      <section className="final-cta">
        <div className="site-wrap center reveal">
          <h2>Ready to check your next lab?</h2>
          <p>Try the free demo on two files, or create an account to see your own submissions and flags.</p>
          <div className="cta-actions">
            <a href="#demo" className="grad-btn big">Check code free</a>
            <Link to="/signup" className="ghost-btn">Create an account</Link>
          </div>
          <div className="cta-checks">
            <span><Icon name="check" size={17} />Free similarity demo</span>
            <span><Icon name="check" size={17} />Two methods + trained classifier</span>
            <span><Icon name="check" size={17} />Code never executed</span>
          </div>
        </div>
      </section>

      <SiteFooter />
    </div>
  );
}
