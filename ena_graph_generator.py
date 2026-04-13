#!/usr/bin/env python3
"""
ENA Graph Generator
====================
Reads ena_relationships.json and produces ena_graph.dot + ena_graph.png

Requirements:
    - Python 3.8+
    - Graphviz installed (brew install graphviz)

Usage:
    python ena_graph_generator.py
    python ena_graph_generator.py --json path/to/ena_relationships.json
    python ena_graph_generator.py --svg   # produce SVG instead of PNG
"""

import json
import subprocess
import argparse
from collections import defaultdict
from pathlib import Path


def load_data(json_path: str) -> tuple:
    with open(json_path) as f:
        data = json.load(f)
    projects        = data["projects"]
    missing_nb      = data["missing_neighbours"]
    return projects, missing_nb


def summarise_missing(missing_nb: dict) -> tuple:
    """Split missing neighbours into unknown children (per parent) and unknown parents."""
    unknown_children = defaultdict(list)   # parent_acc -> [child_accs]
    unknown_parents  = {}                  # acc -> meta

    for acc, meta in missing_nb.items():
        if meta["role"] == "child":
            for parent in meta["referenced_by"]:
                unknown_children[parent].append(acc)
        else:
            unknown_parents[acc] = meta

    return dict(unknown_children), unknown_parents


def build_dot(projects: dict, unknown_children: dict, unknown_parents: dict) -> str:
    lines = [
        "digraph ENA_Projects {",
        "  rankdir=TB;",
        "  compound=true;",
        '  graph [fontname="Helvetica", nodesep=0.5, ranksep=1.0, pad=0.6];',
        '  node  [fontname="Helvetica", fontsize=10, shape=box, style="filled,rounded", margin="0.2,0.12"];',
        '  edge  [fontname="Helvetica", fontsize=9, arrowsize=0.75];',
        "",
    ]

    # ── Unknown parent node(s) ────────────────────────────────────────────────
    for acc, meta in sorted(unknown_parents.items()):
        lines.append(
            f'  "{acc}" [label="{acc}\\n(parent — not in PNG)", '
            f'fillcolor="#FADBD8", color=red, penwidth=2, style="filled,rounded,dashed"];'
        )
    if unknown_parents:
        lines.append("")

    # ── ERGA top-level cluster ────────────────────────────────────────────────
    erga_extra = len(unknown_children.get("PRJEB43510", []))
    lines += [
        "  subgraph cluster_ERGA {",
        '    label="The European Reference Genome Atlas (ERGA)\\nPRJEB43510";',
        '    fontname="Helvetica-Bold"; fontsize=12;',
        '    style="filled,rounded"; fillcolor="#EBF5FB"; color="#2E86C1"; penwidth=2;',
        '    "PRJEB43510" [label="ERGA\\nPRJEB43510", fillcolor="#AED6F1"];',
    ]
    if erga_extra:
        lines.append(
            f'    "ERGA_extra" [label="+{erga_extra} other children\\n(not in PNG)", '
            f'fillcolor="#FADBD8", color=red, penwidth=1.5, style="filled,rounded,dashed", fontsize=9];'
        )
    lines += ["  }", ""]

    # ── ERGA-BGE cluster ──────────────────────────────────────────────────────
    ergabge_extra = len(unknown_children.get("PRJEB61747", []))
    lines += [
        "  subgraph cluster_ERGABGE {",
        '    label="ERGA-BGE\\nPRJEB61747";',
        '    fontname="Helvetica-Bold"; fontsize=11;',
        '    style="filled,rounded"; fillcolor="#EAF4FB"; color="#5DADE2"; penwidth=1.5;',
        '    "PRJEB61747" [label="ERGA-BGE\\nPRJEB61747", fillcolor="#AED6F1"];',
    ]
    if ergabge_extra:
        lines.append(
            f'    "ERGABGE_extra" [label="+{ergabge_extra} genome/assembly\\ndata projects\\n(not in PNG)", '
            f'fillcolor="#FADBD8", color=red, penwidth=1.5, style="filled,rounded,dashed", fontsize=9];'
        )
    lines += ["  }", ""]

    # ── ERGA-BGE APPLICATIONS cluster ─────────────────────────────────────────
    apps_extra = len(unknown_children.get("PRJEB109737", []))
    lines += [
        "  subgraph cluster_APPS {",
        '    label="ERGA-BGE APPLICATIONS\\nPRJEB109737";',
        '    fontname="Helvetica-Bold"; fontsize=11;',
        '    style="filled,rounded"; fillcolor="#FEF9E7"; color="#F39C12"; penwidth=1.5;',
        '    "PRJEB109737" [label="ERGA-BGE APPLICATIONS\\nPRJEB109737", fillcolor="#AED6F1"];',
        '    "PRJEB105536" [label="BGE WP11\\nCricetus cricetus\\npart2\\nPRJEB105536", fillcolor="#FAD7A0"];',
        '    "PRJEB105601" [label="BGE WP11\\nCricetus cricetus\\npart1\\nPRJEB105601", fillcolor="#FAD7A0"];',
    ]
    if apps_extra:
        lines.append(
            f'    "APPS_extra" [label="+{apps_extra} other WP\\ndata projects\\n(not in PNG)", '
            f'fillcolor="#FADBD8", color=red, penwidth=1.5, style="filled,rounded,dashed", fontsize=9];'
        )
    lines += ["  }", ""]

    # ── BGE-metabarcoding cluster (contains Bulk-Sampling sub-cluster) ────────
    lines += [
        "  subgraph cluster_META {",
        '    label="BGE-metabarcoding\\nPRJEB108398";',
        '    fontname="Helvetica-Bold"; fontsize=11;',
        '    style="filled,rounded"; fillcolor="#F4ECF7"; color="#8E44AD"; penwidth=1.5;',
        '    "PRJEB108398" [label="BGE-metabarcoding\\nPRJEB108398", fillcolor="#AED6F1"];',
        '    "PRJEB108475" [label="Ecological Restoration\\nSoil - Chronosequences\\nPRJEB108475", fillcolor="#FAD7A0"];',
        '    "PRJEB108476" [label="Marine Invasive\\nSpecies\\nPRJEB108476", fillcolor="#FAD7A0"];',
        "",
        "    subgraph cluster_BULK {",
        '      label="Bulk-Sampling\\nPRJEB108399";',
        '      fontname="Helvetica"; fontsize=10;',
        '      style="filled,rounded"; fillcolor="#EAF4FB"; color="#8E44AD"; penwidth=1;',
        '      "PRJEB108399" [label="Bulk-Sampling\\nPRJEB108399", fillcolor="#AED6F1"];',
        '      "PRJEB108396" [label="PC\\nPRJEB108396", fillcolor="#FAD7A0"];',
        '      "PRJEB108401" [label="HMS\\nPRJEB108401", fillcolor="#FAD7A0"];',
        "    }",
        "  }",
        "",
    ]

    # ── Orphan nodes (no known parent — BGE umbrella not yet created) ─────────
    lines += [
        '  "PRJEB78703"  [label="BGE genome skimming\\nPRJEB78703",  fillcolor="#FAD7A0"];',
        '  "PRJEB106061" [label="BGE - WP12\\nInsect Pollinators\\nPRJEB106061", fillcolor="#FAD7A0"];',
        "",
    ]

    # ── Edges: known relationships ────────────────────────────────────────────
    known_edges = [
        ("PRJNA533106", "PRJEB43510",  "red",     "dashed"),  # unknown parent
        ("PRJEB43510",  "PRJEB61747",  "#333333", "solid"),
        ("PRJEB43510",  "PRJEB109737", "#333333", "solid"),
        ("PRJEB109737", "PRJEB105536", "#333333", "solid"),
        ("PRJEB109737", "PRJEB105601", "#333333", "solid"),
        ("PRJEB108398", "PRJEB108399", "#333333", "solid"),
        ("PRJEB108398", "PRJEB108475", "#333333", "solid"),
        ("PRJEB108398", "PRJEB108476", "#333333", "solid"),
        ("PRJEB108399", "PRJEB108396", "#333333", "solid"),
        ("PRJEB108399", "PRJEB108401", "#333333", "solid"),
    ]
    lines.append("  // Known edges")
    for src, dst, color, style in known_edges:
        lines.append(f'  "{src}" -> "{dst}" [color="{color}", style={style}];')

    # ── Edges: to collapsed unknown-child summary nodes ───────────────────────
    lines.append("")
    lines.append("  // Collapsed unknown-children summary edges")
    summary_edges = [
        ("PRJEB43510",  "ERGA_extra",    erga_extra),
        ("PRJEB61747",  "ERGABGE_extra", ergabge_extra),
        ("PRJEB109737", "APPS_extra",    apps_extra),
    ]
    for src, dst, count in summary_edges:
        if count:
            lines.append(f'  "{src}" -> "{dst}" [color=red, style=dashed];')

    lines.append("}")
    return "\n".join(lines)


def render(dot_path: str, out_format: str = "png", dpi: int = 150):
    out_path = dot_path.replace(".dot", f".{out_format}")
    cmd = ["dot", f"-T{out_format}"]
    if out_format == "png":
        cmd += [f"-Gdpi={dpi}"]
    cmd += [dot_path, "-o", out_path]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] Graphviz: {result.stderr}")
    else:
        print(f"[OK] Rendered → {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Generate ENA project graph")
    parser.add_argument("--json", default="ena_relationships.json",
                        help="Path to ena_relationships.json (default: ./ena_relationships.json)")
    parser.add_argument("--svg", action="store_true",
                        help="Output SVG instead of PNG")
    parser.add_argument("--dpi", type=int, default=150,
                        help="DPI for PNG output (default: 150)")
    args = parser.parse_args()

    if not Path(args.json).exists():
        print(f"[ERROR] File not found: {args.json}")
        print("  Run ena_project_crawler_v3.py first to generate it.")
        return

    print(f"Loading {args.json} …")
    projects, missing_nb = load_data(args.json)
    unknown_children, unknown_parents = summarise_missing(missing_nb)

    print(f"  Known projects   : {len(projects)}")
    print(f"  Unknown children : { {k: len(v) for k, v in unknown_children.items()} }")
    print(f"  Unknown parents  : {list(unknown_parents.keys())}")

    dot_str  = build_dot(projects, unknown_children, unknown_parents)
    dot_path = "ena_graph.dot"
    with open(dot_path, "w") as f:
        f.write(dot_str)
    print(f"[OK] DOT written  → {dot_path}")

    fmt = "svg" if args.svg else "png"
    render(dot_path, fmt, args.dpi)


if __name__ == "__main__":
    main()
