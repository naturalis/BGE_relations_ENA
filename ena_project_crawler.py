#!/usr/bin/env python3
"""
ENA Umbrella Project Relationship Crawler v3
============================================
Fetches ONLY the accessions known from the PNG diagram.
Reports which relationships exist between them, and which
neighbours (one level up/down) are missing from the PNG.

NO recursive crawling — stops after the seed list.

Usage:
    python ena_project_crawler_v3.py

Output:
    - ena_relationships.json
    - ena_graph.dot  (render with: dot -Tsvg ena_graph.dot -o ena_graph.svg)
    - ena_missing_from_diagram.txt
"""

import urllib.request
import xml.etree.ElementTree as ET
import json
import time

# ── Known accessions from the PNG diagram ─────────────────────────────────────
KNOWN_FROM_PNG = {
    "PRJEB43510",   # ERGA
    "PRJEB78703",   # BGE genome skimming
    "PRJEB108398",  # BGE Metabarcoding Project
    "PRJEB106061",  # Insect pollinators T12.2-3-7
    "PRJEB61747",   # ERGA-BGE
    "PRJEB109737",  # ERGA-BGE APPLICATIONS
    "PRJEB108399",  # Bulk Sampling
    "PRJEB108401",  # High Mountains
    "PRJEB108396",  # Pollinator
    "PRJEB108476",  # Water Sampling
    "PRJEB108475",  # Soil Sampling
    "PRJEB105536",  # WP11
    "PRJEB105601",  # WP11
}

ENA_API = "https://www.ebi.ac.uk/ena/browser/api/xml/{accession}"


def fetch_project_xml(accession: str):
    url = ENA_API.format(accession=accession)
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            raw = resp.read()
        return ET.fromstring(raw)
    except Exception as exc:
        print(f"  [WARN] Could not fetch {accession}: {exc}")
        return None


def parse_project(accession: str, root: ET.Element) -> dict:
    info = {
        "accession": accession,
        "name": accession,
        "is_umbrella": False,
        "children": [],   # all children reported by ENA
        "parents": [],    # all parents reported by ENA
    }

    project_el = root.find(".//PROJECT")
    if project_el is None:
        return info

    name_el  = project_el.find("NAME")
    title_el = project_el.find("TITLE")
    info["name"] = (
        name_el.text  if name_el  is not None and name_el.text  else
        title_el.text if title_el is not None and title_el.text else
        accession
    )

    info["is_umbrella"] = project_el.find("UMBRELLA_PROJECT") is not None

    for rel in project_el.findall(".//RELATED_PROJECTS/RELATED_PROJECT"):
        child_el  = rel.find("CHILD_PROJECT")
        parent_el = rel.find("PARENT_PROJECT")
        if child_el is not None:
            acc = child_el.get("accession")
            if acc:
                info["children"].append(acc.strip())
        if parent_el is not None:
            acc = parent_el.get("accession")
            if acc:
                info["parents"].append(acc.strip())

    info["children"] = list(dict.fromkeys(info["children"]))
    info["parents"]  = list(dict.fromkeys(info["parents"]))
    return info


def fetch_all_seeds(seeds: set) -> dict:
    """Fetch ONLY the seed accessions — no expansion."""
    projects = {}
    for acc in sorted(seeds):
        print(f"  Fetching {acc} …")
        root = fetch_project_xml(acc)
        if root is None:
            projects[acc] = {
                "accession": acc, "name": "?", "is_umbrella": False,
                "children": [], "parents": [],
            }
        else:
            info = parse_project(acc, root)
            projects[acc] = info
            print(f"    name     : {info['name']}")
            print(f"    umbrella : {info['is_umbrella']}")
            print(f"    children : {info['children']}")
            print(f"    parents  : {info['parents']}")
        time.sleep(0.3)
    return projects


def build_edges_and_missing(projects: dict) -> tuple[set, dict]:
    """
    Build edges only between known seeds.
    Collect neighbours that are referenced but NOT in the seed set.
    """
    known = set(projects.keys())
    edges = set()
    missing_neighbours = {}   # acc -> {"referenced_by": [...], "as": "child"|"parent"}

    for acc, info in projects.items():
        for child in info["children"]:
            if child in known:
                edges.add((acc, child))
            else:
                entry = missing_neighbours.setdefault(
                    child, {"referenced_by": [], "role": "child"})
                entry["referenced_by"].append(acc)

        for parent in info["parents"]:
            if parent in known:
                edges.add((parent, acc))
            else:
                entry = missing_neighbours.setdefault(
                    parent, {"referenced_by": [], "role": "parent"})
                entry["referenced_by"].append(acc)

    return edges, missing_neighbours


def wrap(s: str, width: int = 25) -> str:
    words, lines, cur = s.split(), [], ""
    for w in words:
        if cur and len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return "\\n".join(lines)


def write_dot(projects: dict, edges: set, missing_neighbours: dict,
              filename: str = "ena_graph.dot"):
    lines = [
        "digraph ENA_Projects {",
        "  rankdir=BT;",
        '  graph [splines=ortho, nodesep=0.6, ranksep=1.2];',
        '  node [fontname="Helvetica", fontsize=9, width=2.0, height=0.6];',
        '  edge [color="#333333"];',
        "",
        "  // ── Known seed nodes ──",
    ]

    for acc, info in sorted(projects.items()):
        label = wrap(info["name"]) + "\\n" + acc
        fill  = "#AED6F1" if info["is_umbrella"] else "#FAD7A0"
        lines.append(
            f'  "{acc}" [shape=box, style=filled, fillcolor="{fill}", label="{label}"];'
        )

    if missing_neighbours:
        lines += ["", "  // ── Neighbours missing from PNG (shown in red) ──"]
        for nacc, meta in sorted(missing_neighbours.items()):
            role  = meta["role"]
            fill  = "#FADBD8"   # light red
            label = f"{nacc}\\n({role} — not in PNG)"
            lines.append(
                f'  "{nacc}" [shape=box, style=filled, fillcolor="{fill}", '
                f'color=red, penwidth=2, label="{label}"];'
            )

    lines += ["", "  // ── Edges between known nodes ──"]
    for parent, child in sorted(edges):
        lines.append(f'  "{parent}" -> "{child}";')

    if missing_neighbours:
        lines += ["", "  // ── Edges to/from missing neighbours ──"]
        for nacc, meta in sorted(missing_neighbours.items()):
            role = meta["role"]
            for ref in meta["referenced_by"]:
                if role == "child":
                    lines.append(f'  "{ref}" -> "{nacc}" [color=red, style=dashed];')
                else:
                    lines.append(f'  "{nacc}" -> "{ref}" [color=red, style=dashed];')

    lines.append("}")
    with open(filename, "w") as f:
        f.write("\n".join(lines))
    print(f"\n[OK] DOT file written → {filename}")


def write_report(projects: dict, edges: set, missing_neighbours: dict,
                 filename: str = "ena_missing_from_diagram.txt"):
    lines = [
        "ENA Project Graph – Completeness Report",
        "=" * 60,
        "",
        f"Seeds fetched : {len(projects)}",
        f"Edges found between seeds : {len(edges)}",
        f"Neighbours referenced but NOT in PNG : {len(missing_neighbours)}",
        "",
        "EDGES BETWEEN KNOWN PROJECTS:",
    ]
    for p, c in sorted(edges):
        pn = projects.get(p, {}).get("name", "?")
        cn = projects.get(c, {}).get("name", "?")
        lines.append(f"  {p} ({pn})  →  {c} ({cn})")

    lines += ["", "ACCESSIONS REFERENCED BUT MISSING FROM PNG:"]
    if missing_neighbours:
        for nacc, meta in sorted(missing_neighbours.items()):
            refs = ", ".join(meta["referenced_by"])
            lines.append(f"  {nacc}  [as {meta['role']} of: {refs}]")
    else:
        lines.append("  (none — PNG appears complete for these seeds)")

    with open(filename, "w") as f:
        f.write("\n".join(lines))
    print(f"[OK] Report written → {filename}")


def main():
    print("=" * 60)
    print("ENA Project Crawler v3 — seed-only, no BFS expansion")
    print("=" * 60)
    print(f"\nFetching {len(KNOWN_FROM_PNG)} seed accessions …\n")

    projects           = fetch_all_seeds(KNOWN_FROM_PNG)
    edges, missing_nb  = build_edges_and_missing(projects)

    print("\n" + "=" * 60)
    print(f"Edges between known seeds : {len(edges)}")
    print(f"Missing neighbours        : {len(missing_nb)}")

    if missing_nb:
        print("\nAccessions referenced but NOT in PNG:")
        for nacc, meta in sorted(missing_nb.items()):
            print(f"  {nacc}  (as {meta['role']} of {meta['referenced_by']})")

    with open("ena_relationships.json", "w") as f:
        json.dump({
            "projects": projects,
            "edges": [list(e) for e in edges],
            "missing_neighbours": missing_nb,
        }, f, indent=2)
    print("\n[OK] JSON written → ena_relationships.json")

    write_dot(projects, edges, missing_nb, "ena_graph.dot")
    write_report(projects, edges, missing_nb, "ena_missing_from_diagram.txt")

    print("\nRender with:")
    print("  dot -Tsvg ena_graph.dot -o ena_graph.svg")
    print("  dot -Tpng -Gdpi=150 ena_graph.dot -o ena_graph.png")
    print("\nDone.")


if __name__ == "__main__":
    main()
