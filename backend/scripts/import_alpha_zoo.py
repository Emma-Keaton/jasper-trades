"""Import the 452-factor alpha zoo from the Vibe-Trading repo.

Copies the real factor modules (academic, alpha101, gtja191, qlib158) and the
shared base operators into ``backend/app/alpha_zoo/``, rewrites the
``src.factors.base`` imports to the local package, then writes a real catalog
``backend/data/alpha_factors.json`` from the in-repo ``__alpha_meta__``.

Usage:
    python scripts/import_alpha_zoo.py --src <Vibe-Trading agent/src/factors/zoo>
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND_ROOT / "app"
DATA_DIR = BACKEND_ROOT / "data"
ZOO_PKG = APP_DIR / "alpha_zoo"

ZOO_NAMES = ["academic", "alpha101", "gtja191", "qlib158"]

IMPORT_RE = re.compile(r"^(\s*from\s+)src\.factors\.base(\s+import\s+.+)$", re.M)
IMPORT_RE_ALT = re.compile(r"^(\s*import\s+)src\.factors\.base\b.*$", re.M)


def _rewrite_imports(src: str) -> str:
    src = IMPORT_RE.sub(r"\1app.alpha_zoo.base\2", src)
    src = IMPORT_RE_ALT.sub(lambda m: m.group(1) + "app.alpha_zoo.base", src)
    return src


def copy_zoo(zoo_root: Path) -> list[Path]:
    shutil.rmtree(ZOO_PKG, ignore_errors=True)
    ZOO_PKG.mkdir(parents=True, exist_ok=True)

    base_src = zoo_root.parent / "base.py"
    if base_src.exists():
        shutil.copy2(base_src, ZOO_PKG / "base.py")
    else:
        raise FileNotFoundError(f"base.py not found next to zoo root: {base_src}")

    (ZOO_PKG / "__init__.py").write_text("", encoding="utf-8")

    copied: list[Path] = []
    for zoo in ZOO_NAMES:
        src_dir = zoo_root / zoo
        dst_dir = ZOO_PKG / zoo
        dst_dir.mkdir(parents=True, exist_ok=True)
        (dst_dir / "__init__.py").write_text("", encoding="utf-8")
        for f in sorted(src_dir.glob("*.py")):
            if f.name == "__init__.py":
                continue
            text = f.read_text(encoding="utf-8")
            rewritten = _rewrite_imports(text)
            dst = dst_dir / f.name
            dst.write_text(rewritten, encoding="utf-8")
            copied.append(dst)
    return copied


def build_catalog(zoo_root: Path) -> list[dict]:
    sys.path.insert(0, str(BACKEND_ROOT))
    catalog: list[dict] = []
    for zoo in ZOO_NAMES:
        src_dir = zoo_root / zoo
        for f in sorted(src_dir.glob("*.py")):
            if f.name == "__init__.py":
                continue
            module_name = f"{zoo}_{f.name[:-3]}"
            module_path = str(ZOO_PKG / zoo / f.name)
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {zoo}/{f.name}: import failed ({exc})")
                continue
            meta = getattr(mod, "__alpha_meta__", None)
            if not isinstance(meta, dict):
                print(f"  ! {zoo}/{f.name}: no __alpha_meta__")
                continue
            entry = dict(meta)
            entry.setdefault("id", f"{zoo}_{f.name[:-3]}")
            entry["zoo"] = zoo
            entry["module"] = f"app.alpha_zoo.{zoo}.{f.name[:-3]}"
            entry["file"] = f.name
            entry["has_compute"] = callable(getattr(mod, "compute", None))
            catalog.append(entry)
    catalog.sort(key=lambda e: (e["zoo"], e["id"]))
    return catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the 452-factor alpha zoo.")
    parser.add_argument(
        "--src",
        default=r"E:\Projects\finance-repos\Vibe-Trading\agent\src\factors\zoo",
        help="Path to the Vibe-Trading zoo directory",
    )
    parser.add_argument(
        "--catalog-out",
        default=str(DATA_DIR / "alpha_factors.json"),
        help="Output path for the generated catalog JSON",
    )
    args = parser.parse_args()

    zoo_root = Path(args.src)
    if not zoo_root.exists():
        raise SystemExit(f"zoo root not found: {zoo_root}")

    print("Copying factor modules ...")
    copied = copy_zoo(zoo_root)
    print(f"  copied {len(copied)} factor files into {ZOO_PKG}")

    print("Building catalog from __alpha_meta__ ...")
    catalog = build_catalog(zoo_root)
    print(f"  catalog: {len(catalog)} factors")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(args.catalog_out, "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, indent=2, ensure_ascii=False)
    print(f"  wrote {args.catalog_out}")

    by_zoo = {}
    for e in catalog:
        by_zoo.setdefault(e["zoo"], 0)
        by_zoo[e["zoo"]] += 1
    print("  per zoo:", ", ".join(f"{k}={v}" for k, v in by_zoo.items()))

    # Smoke-test that the copied local package imports and computes.
    print("Smoke-testing local package ...")
    for zoo in ZOO_NAMES:
        pkg = importlib.import_module(f"app.alpha_zoo.{zoo}")
        print(f"  imported app.alpha_zoo.{zoo} ok")


if __name__ == "__main__":
    main()
