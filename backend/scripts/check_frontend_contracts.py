"""Compare every frontend API literal against the backend OpenAPI spec.

Run from backend/:  python scripts/check_frontend_contracts.py

Exits non-zero when the frontend calls a route the backend does not serve. Written
to a file rather than inline because the pattern matching uses backslashes and
dollar braces that shells mangle.
"""

import io
import contextlib
import logging
import pathlib
import re
import sys


def main() -> int:
    logging.disable(logging.CRITICAL)
    with contextlib.redirect_stdout(io.StringIO()):
        import app.main as main_module

    server = set(main_module.app.openapi()["paths"])

    frontend = pathlib.Path(__file__).resolve().parent.parent.parent / "frontend"
    literal = re.compile(r"['\"`](/api/v1/[^'\"`\s]*)")
    template_var = re.compile(r"\$\{[^}]*\}")

    # Strip block and line comments before scanning. Without this, a comment that
    # quotes an old URL ("was '/api/v1/backtest/results'") is reported as a live
    # call, which is how this script reported a bug it had just been used to fix.
    block_comment = re.compile(r"/\*.*?\*/", re.DOTALL)
    line_comment = re.compile(r"^\s*//.*$", re.MULTILINE)

    calls: dict[str, set[str]] = {}
    for path in frontend.rglob("*"):
        if path.suffix not in (".ts", ".tsx") or "node_modules" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        text = block_comment.sub("", text)
        text = line_comment.sub("", text)
        for raw in literal.findall(text):
            calls.setdefault(raw, set()).add(path.name)

    def resolves(candidate: str) -> bool:
        # A template literal may carry a path parameter (`/swarm/${runId}`) or an
        # appended query string (`/alpha-factors${params}`, where params starts with
        # "?"). Both become `{v}`; the trailing-strip form is a fallback for the
        # query case only, and is tried last because it also matches the path case
        # incorrectly (/swarm would be accepted if /swarm existed).
        head = candidate.split("?")[0]
        variants = [template_var.sub("{v}", head)]

        stripped = re.sub(r"\$\{[^}]*\}$", "", head)
        if stripped != head:
            variants.append(stripped)

        # FastAPI registers a trailing slash literally, so both spellings are tried
        # rather than stripping one and missing the other.
        expanded: list[str] = []
        for variant in variants:
            for spelling in {variant, variant.rstrip("/"), variant + "/"}:
                if spelling and spelling not in expanded:
                    expanded.append(spelling)

        for spelling in expanded:
            if spelling in server:
                return True
            pattern = "^" + "/".join(
                re.escape(seg) if not seg.startswith("{v") else r"[^/]+"
                for seg in spelling.split("/")
            ) + "$"
            if any(re.match(pattern, sp) for sp in server):
                return True
        return False

    unmatched = [(p, sorted(f)) for p, f in sorted(calls.items()) if not resolves(p)]

    print(f"backend routes: {len(server)}")
    print(f"frontend api literals: {len(calls)}")
    print(f"unmatched: {len(unmatched)}")
    for path, files in unmatched:
        print(f"  MISSING {path}  <- {', '.join(files[:2])}")

    return 1 if unmatched else 0


if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    raise SystemExit(main())
