#!/usr/bin/env python3
"""Validate addon external Python dependencies against requirements files.

This checks every addons/*/__manifest__.py and reads:
    external_dependencies = {"python": [...]}

Any dependency declared there must exist in:
    - requirements.txt, or
    - requirements-local.txt

Use --sync to auto-add missing dependencies to requirements-local.txt.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


DEFAULT_HEADER = "# Extra Python dependencies required by custom addons."


def canonicalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def extract_requirement_name(requirement_line: str) -> str | None:
    line = requirement_line.strip()
    if not line or line.startswith("#") or line.startswith("-"):
        return None
    line = line.split("#", 1)[0].strip()
    if not line:
        return None
    match = re.match(r"^\s*([A-Za-z0-9_.-]+)", line)
    if not match:
        return None
    return match.group(1)


def read_requirements_names(*paths: Path) -> Set[str]:
    names: Set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            name = extract_requirement_name(raw_line)
            if name:
                names.add(canonicalize(name))
    return names


def load_manifest(path: Path) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in reversed(tree.body):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Dict):
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            return ast.literal_eval(node.value)
    raise ValueError(f"Could not parse manifest dict from {path}")


def collect_external_python_dependencies(addons_dir: Path) -> Dict[str, Tuple[str, Set[str]]]:
    deps: Dict[str, Tuple[str, Set[str]]] = {}
    for manifest_path in sorted(addons_dir.glob("*/__manifest__.py")):
        manifest = load_manifest(manifest_path)
        external = manifest.get("external_dependencies") or {}
        if not isinstance(external, dict):
            continue
        python_deps = external.get("python") or []
        if isinstance(python_deps, str):
            python_deps = [python_deps]
        if not isinstance(python_deps, list):
            continue

        addon_name = manifest_path.parent.name
        for dep in python_deps:
            if not isinstance(dep, str) or not dep.strip():
                continue
            dep = dep.strip()
            canon = canonicalize(dep)
            if canon not in deps:
                deps[canon] = (dep, set())
            deps[canon][1].add(addon_name)
    return deps


def read_requirements_local(path: Path) -> Tuple[List[str], Dict[str, str]]:
    comments: List[str] = []
    lines: Dict[str, str] = {}
    if not path.exists():
        return [DEFAULT_HEADER], {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            comments.append(line)
            continue
        name = extract_requirement_name(line)
        if not name:
            continue
        lines[canonicalize(name)] = line

    if not comments:
        comments = [DEFAULT_HEADER]
    return comments, lines


def write_requirements_local(path: Path, comments: List[str], requirements: Dict[str, str]) -> None:
    ordered = [requirements[k] for k in sorted(requirements)]
    content = "\n".join(comments + ordered) + "\n"
    path.write_text(content, encoding="utf-8")


def format_missing(missing: Dict[str, Tuple[str, Set[str]]]) -> str:
    lines = ["Missing addon external Python dependencies in requirements files:"]
    for canon in sorted(missing):
        dep, addons = missing[canon]
        addon_list = ", ".join(sorted(addons))
        lines.append(f"  - {dep} (required by: {addon_list})")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--addons-dir", default="addons", help="Path to addons directory")
    parser.add_argument(
        "--requirements-core",
        default="requirements.txt",
        help="Path to core requirements file",
    )
    parser.add_argument(
        "--requirements-local",
        default="requirements-local.txt",
        help="Path to local requirements file",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Auto-add missing dependencies to requirements-local.txt",
    )
    args = parser.parse_args()

    addons_dir = Path(args.addons_dir)
    req_core = Path(args.requirements_core)
    req_local = Path(args.requirements_local)

    declared = collect_external_python_dependencies(addons_dir)
    available = read_requirements_names(req_core, req_local)

    missing = {k: v for k, v in declared.items() if k not in available}

    if args.sync and missing:
        comments, local_lines = read_requirements_local(req_local)
        for canon, (dep_name, _addons) in missing.items():
            local_lines.setdefault(canon, dep_name)
        write_requirements_local(req_local, comments, local_lines)
        print(f"Updated {req_local} with {len(missing)} missing dependencies.")
        available = read_requirements_names(req_core, req_local)
        missing = {k: v for k, v in declared.items() if k not in available}

    if missing:
        print(format_missing(missing), file=sys.stderr)
        print(
            "\nRun with --sync to auto-add missing dependencies to requirements-local.txt.",
            file=sys.stderr,
        )
        return 1

    print("Addon external dependencies are fully covered by requirements files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
