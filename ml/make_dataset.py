"""Build the labelled set: hand-written originals plus generated copies.

For every original in data/originals/ this writes four copies to
data/copies/, one of each kind named in the design document:

  unchanged     - same code; only comments and blank lines differ
  renamed       - every user-defined name replaced
  reordered     - functions/methods shuffled, then renamed
  restructured  - for-range loops become while loops, if/else branches
                  are swapped, x += y becomes x = x + y, script code is
                  wrapped in main(), then renamed
  partial       - (extra, harder) about 60% of the original's top-level
                  code, renamed, mixed with code from an unrelated original

Copies are made by rewriting the syntax tree, so they are valid Python.
Run:  python ml/make_dataset.py
"""
from __future__ import annotations

import ast
import builtins
import keyword
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIGINALS = HERE / "data" / "originals"
COPIES = HERE / "data" / "copies"
KINDS = ("unchanged", "renamed", "reordered", "restructured", "partial")

WORDS = ["data", "temp", "val", "res", "item", "arr", "total", "cnt", "num", "lst", "buf", "acc",
         "elem", "key", "out", "info", "store", "box", "rec", "node", "obj", "mem", "part", "seq",
         "my", "the", "new", "calc", "get", "do", "run", "check", "make", "find", "x", "y", "z"]
RESERVED = set(dir(builtins)) | set(keyword.kwlist) | {"self", "cls", "main"}


# ------------------------------------------------------------------ renaming

def user_names(tree: ast.Module) -> set[str]:
    imported = set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imported |= {(a.asname or a.name).split(".")[0] for a in node.names}
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
    return {n for n in names - imported - RESERVED if not n.startswith("__")}


class Renamer(ast.NodeTransformer):
    def __init__(self, mapping: dict[str, str]):
        self.m = mapping

    def visit_Name(self, node):
        node.id = self.m.get(node.id, node.id)
        return node

    def visit_arg(self, node):
        node.arg = self.m.get(node.arg, node.arg)
        return node

    def visit_FunctionDef(self, node):
        node.name = self.m.get(node.name, node.name)
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node):
        node.name = self.m.get(node.name, node.name)
        self.generic_visit(node)
        return node

    def visit_keyword(self, node):
        if node.arg:
            node.arg = self.m.get(node.arg, node.arg)
        self.generic_visit(node)
        return node

    def visit_ExceptHandler(self, node):
        if node.name:
            node.name = self.m.get(node.name, node.name)
        self.generic_visit(node)
        return node


def rename(tree: ast.Module, rng: random.Random) -> ast.Module:
    taken = set(RESERVED)
    mapping = {}
    for name in sorted(user_names(tree)):
        while True:
            new = rng.choice(WORDS) + rng.choice(["", "_", "s"]) + rng.choice(["", str(rng.randint(1, 9)), rng.choice(WORDS)])
            if new not in taken and new.isidentifier() and not keyword.iskeyword(new):
                break
        taken.add(new)
        mapping[name] = new
    return Renamer(mapping).visit(tree)


# ------------------------------------------------------------------ reordering

def reorder(tree: ast.Module, rng: random.Random) -> ast.Module:
    def shuffle_defs(body: list, keep_first_init: bool) -> list:
        slots = [i for i, n in enumerate(body) if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                 and not (keep_first_init and getattr(n, "name", "") == "__init__")]
        defs = [body[i] for i in slots]
        if len(defs) > 1:
            original = list(defs)
            while defs == original:
                rng.shuffle(defs)
        out = list(body)
        for i, node in zip(slots, defs):
            out[i] = node
        return out

    tree.body = shuffle_defs(tree.body, False)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            node.body = shuffle_defs(node.body, True)
    return tree


# ------------------------------------------------------------------ restructuring

class Restructure(ast.NodeTransformer):
    def visit_For(self, node):
        self.generic_visit(node)
        it = node.iter
        simple = (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == "range"
                  and 1 <= len(it.args) <= 2 and not it.keywords and isinstance(node.target, ast.Name)
                  and not node.orelse and not any(isinstance(n, ast.Continue) for n in ast.walk(node)))
        if not simple:
            return node
        start = it.args[0] if len(it.args) == 2 else ast.Constant(0)
        stop = it.args[-1]
        var = node.target.id
        init = ast.Assign(targets=[ast.Name(var, ast.Store())], value=start)
        step = ast.AugAssign(target=ast.Name(var, ast.Store()), op=ast.Add(), value=ast.Constant(1))
        loop = ast.While(test=ast.Compare(ast.Name(var, ast.Load()), [ast.Lt()], [stop]),
                         body=node.body + [step], orelse=[])
        return [init, loop]

    def visit_If(self, node):
        self.generic_visit(node)
        is_elif_chain = len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)
        if node.orelse and not is_elif_chain:
            node.test = ast.UnaryOp(ast.Not(), node.test)
            node.body, node.orelse = node.orelse, node.body
        return node

    def visit_AugAssign(self, node):
        if isinstance(node.target, ast.Name) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
            return ast.Assign(targets=[ast.Name(node.target.id, ast.Store())],
                              value=ast.BinOp(ast.Name(node.target.id, ast.Load()), node.op, node.value))
        return node


def wrap_in_main(tree: ast.Module) -> ast.Module:
    """Move top-level script statements into main(), if no function reads those globals."""
    head, script = [], []
    for n in tree.body:
        is_def = isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef))
        is_constant = isinstance(n, ast.Assign) and isinstance(n.value, (ast.Constant, ast.List, ast.Tuple,
                                                                          ast.Dict, ast.Lambda))
        # constants count as setup only before the first script statement
        (head if is_def or (is_constant and not script) else script).append(n)
    if not script or any(isinstance(n, ast.If) and "__name__" in ast.unparse(n.test) for n in script):
        return tree
    script_globals = {t.id for n in script for t in ast.walk(n) if isinstance(t, ast.Name) and isinstance(t.ctx, ast.Store)}
    read_in_defs = {t.id for n in head if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                    for t in ast.walk(n) if isinstance(t, ast.Name)}
    if script_globals & read_in_defs:
        return tree
    main = ast.FunctionDef(name="main", args=ast.arguments([], [], None, [], [], None, []), body=script,
                           decorator_list=[], returns=None, type_params=[])
    guard = ast.parse('if __name__ == "__main__":\n    main()').body[0]
    tree.body = head + [main, guard]
    return tree


# ------------------------------------------------------------------ main

def partial_copy(source: str, filler: str, rng: random.Random) -> str:
    body = ast.parse(source).body
    keep = max(1, round(len(body) * 0.6))
    start = rng.randint(0, len(body) - keep)
    tree = ast.Module(body=body[start:start + keep], type_ignores=[])
    tree = rename(tree, rng)
    other = ast.parse(filler).body
    extra = other[: max(1, len(other) // 2)]
    tree.body = extra + tree.body if rng.random() < 0.5 else tree.body + extra
    return ast.unparse(ast.fix_missing_locations(tree)) + "\n"


def make_copy(source: str, kind: str, rng: random.Random, filler: str = "") -> str:
    if kind == "partial":
        return partial_copy(source, filler, rng)
    if kind == "unchanged":
        lines = source.splitlines()
        out = ["# Lab submission", ""]
        for line in lines:
            out.append(line)
            if line.strip() and rng.random() < 0.15:
                out.append("")
        return "\n".join(out) + "\n"
    tree = ast.parse(source)
    if kind == "reordered":
        tree = reorder(tree, rng)
    if kind == "restructured":
        tree = Restructure().visit(tree)
        tree = wrap_in_main(tree)
    tree = rename(tree, rng)
    return ast.unparse(ast.fix_missing_locations(tree)) + "\n"


def main() -> None:
    rng = random.Random(2026)
    COPIES.mkdir(parents=True, exist_ok=True)
    for old in COPIES.glob("*.py"):
        old.unlink()
    count = 0
    originals = sorted(ORIGINALS.glob("*.py"))
    for original in originals:
        source = original.read_text()
        others = [o for o in originals if o.name[:3] != original.name[:3]]
        for kind in KINDS:
            text = make_copy(source, kind, rng, rng.choice(others).read_text())
            ast.parse(text)   # every copy must still be valid Python
            (COPIES / f"{original.stem}__{kind}.py").write_text(text)
            count += 1
    print(f"wrote {count} copies of {len(list(ORIGINALS.glob('*.py')))} originals to {COPIES}")


if __name__ == "__main__":
    main()
