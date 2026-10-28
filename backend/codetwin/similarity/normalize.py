"""Step 1: turn source code into a normalised token stream.

Every identifier becomes ID and every literal becomes LIT; keywords and
operators stay. Comments, blank lines and formatting are dropped, so
renaming variables or reformatting makes no difference. The code is only
tokenised, never imported or run.
"""
from __future__ import annotations

import io
import keyword
import re
import token
import tokenize
from dataclasses import dataclass


@dataclass(frozen=True)
class Tok:
    text: str
    line: int


_SKIP = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.ENCODING, tokenize.ENDMARKER}
_FSTRING_START = getattr(token, "FSTRING_START", None)
_FSTRING_END = getattr(token, "FSTRING_END", None)
_TSTRING_START = getattr(token, "TSTRING_START", None)
_TSTRING_END = getattr(token, "TSTRING_END", None)
_SOFT_KEYWORDS = set(getattr(keyword, "softkwlist", []))


def normalize(source: str) -> list[Tok]:
    try:
        return _with_tokenize(source)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return _with_regex(source)


def _with_tokenize(source: str) -> list[Tok]:
    out: list[Tok] = []
    depth = 0   # inside an f-string the whole thing counts as one literal
    for t in tokenize.generate_tokens(io.StringIO(source).readline):
        if t.type in (_FSTRING_START, _TSTRING_START):
            if depth == 0:
                out.append(Tok("LIT", t.start[0]))
            depth += 1
            continue
        if t.type in (_FSTRING_END, _TSTRING_END):
            depth -= 1
            continue
        if depth or t.type in _SKIP:
            continue
        if t.type == tokenize.NAME:
            is_kw = keyword.iskeyword(t.string) or t.string in _SOFT_KEYWORDS
            out.append(Tok(t.string if is_kw else "ID", t.start[0]))
        elif t.type in (tokenize.NUMBER, tokenize.STRING):
            out.append(Tok("LIT", t.start[0]))
        elif t.type == tokenize.INDENT:
            out.append(Tok("INDENT", t.start[0]))
        elif t.type == tokenize.DEDENT:
            out.append(Tok("DEDENT", t.start[0]))
        elif t.type == tokenize.OP:
            out.append(Tok(t.string, t.start[0]))
    return out


_REGEX = re.compile(r"""(?P<str>(?:[rbuf]{0,2})("{3}[\s\S]*?"{3}|'{3}[\s\S]*?'{3}|"[^"\n]*"|'[^'\n]*'))"""
                    r"""|(?P<num>\d[\w.]*)|(?P<name>[A-Za-z_]\w*)|(?P<comment>\#[^\n]*)|(?P<op>[^\s\w])""")


def _with_regex(source: str) -> list[Tok]:
    """Fallback for files Python cannot tokenise (for example a syntax error)."""
    out: list[Tok] = []
    for m in _REGEX.finditer(source):
        line = source.count("\n", 0, m.start()) + 1
        kind = m.lastgroup
        if kind == "comment":
            continue
        if kind in ("str", "num"):
            out.append(Tok("LIT", line))
        elif kind == "name":
            out.append(Tok(m.group() if keyword.iskeyword(m.group()) else "ID", line))
        else:
            out.append(Tok(m.group(), line))
    return out
