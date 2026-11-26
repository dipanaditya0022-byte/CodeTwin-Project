// Shared pieces of the public pages: logo, header and footer.
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

export function LogoMark({ size = 36 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" aria-hidden="true" className="logo-mark">
      <rect width="36" height="36" rx="7" fill="#1b2430" />
      {/* two code brackets around a highlighted mark: a submission and its twin */}
      <path d="M14 11l-6 7 6 7" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M22 11l6 7-6 7" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="15" y="15.5" width="6" height="5" rx="1" fill="#ffe066" />
    </svg>
  );
}

export function Logo({ light = false }) {
  const { pathname, hash } = useLocation();
  const toTop = () => {
    const smooth = !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: smooth ? "smooth" : "auto" });
  };

  function onClick(e) {
    if (pathname === "/") {
      // already home: just go back to the top, and drop any #section from the address bar
      e.preventDefault();
      if (hash) window.history.replaceState(null, "", "/");
      toTop();
    } else {
      window.setTimeout(() => window.scrollTo(0, 0), 0);
    }
  }

  return (
    <Link to="/" onClick={onClick} className={`site-logo${light ? " site-logo-light" : ""}`} aria-label="CodeTwin home, back to top">
      <LogoMark />
      <span>Code<b>Twin</b></span>
    </Link>
  );
}

export function SiteHeader() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className={`site-header${scrolled ? " is-scrolled" : ""}`}>
      <div className="site-wrap site-header-row">
        <Logo />
        <nav className="site-nav" aria-label="Sections">
          <a href="#pipeline">Pipeline</a>
          <a href="#features">Features</a>
          <a href="#compare">Compare</a>
          <a href="#different">Why CodeTwin</a>
          <a href="#faq">FAQ</a>
        </nav>
        <div className="site-header-actions">
          <Link to="/login" className="text-link">Log in</Link>
          <Link to="/signup" className="grad-btn">Get started</Link>
        </div>
      </div>
    </header>
  );
}

const FOOTER = [
  ["Product", [["Similarity demo", "/#demo"], ["Pipeline", "/#pipeline"], ["Features", "/#features"], ["Compare", "/#compare"], ["FAQ", "/#faq"]]],
  ["Account", [["Log in", "/login"], ["Create an account", "/signup"]]],
  ["For", [["Teachers", "/#roles"], ["Students", "/#roles"], ["Administrators", "/#roles"]]],
  ["Built with", [["Python · FastAPI", null], ["React", null], ["Microsoft Azure", null], ["UniXcoder · scikit-learn", null]]],
];

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-wrap site-footer-grid">
        <div className="site-footer-brand">
          <Logo light />
          <p>Code similarity checking and fair review for Python programming labs.</p>
        </div>
        {FOOTER.map(([title, links]) => (
          <div key={title}>
            <h4>{title}</h4>
            {links.map(([label, to]) => to
              ? (to.startsWith("/#") ? <a key={label} href={to}>{label}</a> : <Link key={label} to={to}>{label}</Link>)
              : <span key={label}>{label}</span>)}
          </div>
        ))}
      </div>
      <div className="site-wrap site-footer-bottom">
        <span>© 2026 CodeTwin</span>
        <span>Prior work: MOSS, JPlag, Dolos · Winnowing: Schleimer, Wilkerson and Aiken, 2003</span>
      </div>
    </footer>
  );
}
