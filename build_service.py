#!/usr/bin/env python3
"""
Generate service.html from service.csv + service_raw.html.

- Input:  service.csv (TSV-style, tab-delimited)
- Input:  service_raw.html (contains <!-- SERVICE:START --> ... <!-- SERVICE:END -->)
- Output: service.html
"""

from __future__ import annotations

import csv
import html
import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


CSV_PATH = Path("service.csv")
RAW_HTML_PATH = Path("service_raw.html")
OUT_HTML_PATH = Path("service.html")

START_MARKER = "<!-- SERVICE:START -->"
END_MARKER = "<!-- SERVICE:END -->"


@dataclass(frozen=True)
class ServiceRow:
    section: str
    role: str
    venue: str
    track: str
    show_year: bool
    venue_full: str
    organization: str
    start_year: int
    end_year: int


def _parse_bool(s: str) -> bool:
    return s.strip().lower() in {"true", "1", "yes", "y"}


def _year_range(start: int, end: int) -> str:
    return f"{start}" if start == end else f"{start}\u2013{end}"  # en-dash


def _sc(text: str) -> str:
    """Small-caps span with HTML escaping."""
    return f'<span class="sc">{html.escape(text)}</span>'


def _em(text: str) -> str:
    """Italic with HTML escaping."""
    return f"<em>{html.escape(text)}</em>"


def _needs_sc(venue: str) -> bool:
    """
    Heuristic: if venue looks like an acronym/event code or includes a year,
    wrap it in small caps for your style.
    """
    v = venue.strip()
    if not v:
        return False
    if any(ch.isdigit() for ch in v):
        return True
    if v.isupper() and len(v) <= 12:
        return True
    # Common cases like "IEEE VR"
    if len(v.split()) <= 3 and any(tok.isupper() for tok in v.split()):
        return True
    return False


def _format_li(row: ServiceRow) -> str:
    """
    Format one <li> using conventions inferred from your existing service.html:
    - Conference org entries: "Role, <SC ORG> Venue Full (<SC Venue Year>)"
    - Peer review entries:
        - If venue_full looks like a journal/magazine: "Reviewer, <em>Journal</em> (Year)"
        - Otherwise: "Track Reviewer, <SC ORG> Venue Full (<SC Venue YearRange>)"
    - Other/community: "Role, Venue Full (<SC Venue>), Organization (YearRange)"  (close to your example)
    """
    section = row.section.strip()
    role = row.role.strip()
    venue = row.venue.strip()
    track = row.track.strip()
    venue_full = row.venue_full.strip()
    org = row.organization.strip()
    years = _year_range(row.start_year, row.end_year)

    # In your sample, CHI reviewing uses a combined year range in the parentheses.
    # We'll always compute from start/end; show_year controls whether to show it.
    year_suffix = f"&nbsp;({years})" if row.show_year else ""

    # For events like "CHI 2023–2026" you used small-caps inside parentheses.
    # We'll build a "(<SC venue yearRange>)" block when not show_year (i.e., conference-style).
    venue_year_block = ""
    if not row.show_year:
        # When venue already contains a year (e.g., "CHI 2023; CHI 2024; ..."), prefer computed range.
        # Build something like: (<span class="sc">CHI&nbsp;2023–2026</span>)
        # Preserve nonbreaking spaces in "ASSETS 2026" style.
        label = venue
        # If venue ends with a year or contains it, replace with computed range for consistency.
        # Examples:
        #   venue="ASSETS 2026" -> "ASSETS 2026"
        #   venue="CHI 2026" -> "CHI 2026"
        #   venue="CHI 2023; CHI 2024; ..." -> "CHI 2023–2026"
        base = re.split(r"[;,(]", venue)[0].strip()
        if base.upper().startswith("CHI"):
            label = f"CHI\u00a0{years}"
        else:
            # If venue already has a year and it's a single-year entry, keep it.
            # Otherwise, attach computed years.
            if any(ch.isdigit() for ch in venue) and row.start_year == row.end_year:
                label = venue.replace(" ", "\u00a0")
            else:
                label = f"{venue}\u00a0{years}".replace(" ", "\u00a0")
        venue_year_block = f" ({_sc(label)})"

    if section == "Conference Organization":
        parts = []
        if role:
            parts.append(html.escape(role))
        # Organization in small caps, then venue_full
        if org:
            parts.append(_sc(org))
        if venue_full:
            parts.append(html.escape(venue_full))
        # Track (if any) typically comes after role in your hand-coded version for CHI AC lines.
        # But your example places track after role: "Associate Chair, Poster Track, ACM Conference..."
        if track:
            # Insert track after role (first element)
            # Rebuild cleanly: "Role, Track, <SC ORG> Venue Full (…)"
            head = ", ".join([html.escape(role), html.escape(track)]) if role else html.escape(track)
            tail = ", ".join([_sc(org), html.escape(venue_full)]) if org and venue_full else html.escape(venue_full or org)
            return f"<li>{head}, {tail}{venue_year_block}</li>"
        return f"<li>{', '.join(parts)}{venue_year_block}</li>"

    if section == "Peer Review":
        # If venue_full looks like a journal/magazine title, match your style:
        # "Reviewer, <em>Interacting with Computers</em>&nbsp;(2026)"
        is_journalish = bool(venue_full) and ("conference" not in venue_full.lower())
        if is_journalish and row.show_year:
            prefix = html.escape(role) if role else "Reviewer"
            return f"<li>{prefix}, {_em(venue_full)}{year_suffix}</li>"

        # Otherwise conference-style reviewing:
        # "Technical Paper Reviewer, <SC ORG> Venue Full (<SC VENUE 2023–2026>)"
        prefix = html.escape(role) if role else "Reviewer"
        if track and not role:
            prefix = html.escape(track)
        elif track and role:
            # If both exist and role doesn't already include track phrasing, keep role then (optionally) track.
            # To mirror your CHI reviewer line, prefer role first, skip repeating track if role already implies it.
            if track.lower() not in role.lower():
                prefix = f"{html.escape(role)}"
            else:
                prefix = html.escape(role)

        tail = ""
        if org and venue_full:
            tail = f"{_sc(org)} {html.escape(venue_full)}"
        else:
            tail = html.escape(venue_full or org or venue)

        return f"<li>{prefix}, {tail}{venue_year_block}</li>"

    # Default for other sections (e.g., Community & Professional Service)
    # Try to mirror: "Role, Venue Full (<SC Venue>), Organization (2022–2024)"
    role_txt = html.escape(role) if role else ""
    venue_full_txt = html.escape(venue_full) if venue_full else ""
    venue_sc = _sc(venue) if venue else ""
    org_txt = html.escape(org) if org else ""

    chunks = []
    if role_txt:
        chunks.append(role_txt)
    if venue_full_txt:
        chunks.append(venue_full_txt)
    if venue_sc:
        chunks.append(f"({venue_sc})")
    if org_txt:
        chunks.append(org_txt)
    if years:
        chunks.append(f"({years})")

    return f"<li>{', '.join(chunks)}</li>"


def read_rows(path: Path) -> list[ServiceRow]:
    text = path.read_text(encoding="utf-8")
    # Your CSV is tab-delimited.
    reader = csv.DictReader(text.splitlines(), delimiter="\t")
    rows: list[ServiceRow] = []
    for r in reader:
        rows.append(
            ServiceRow(
                section=(r.get("section") or "").strip(),
                role=(r.get("role") or "").strip(),
                venue=(r.get("venue") or "").strip(),
                track=(r.get("track") or "").strip(),
                show_year=_parse_bool(r.get("show_year") or "false"),
                venue_full=(r.get("venue_full") or "").strip(),
                organization=(r.get("organization") or "").strip(),
                start_year=int((r.get("start_year") or "0").strip() or "0"),
                end_year=int((r.get("end_year") or "0").strip() or "0"),
            )
        )
    return rows


def build_service_html(rows: list[ServiceRow]) -> str:
    # Preserve section order as it appears in the CSV
    grouped: "OrderedDict[str, list[ServiceRow]]" = OrderedDict()
    for row in rows:
        grouped.setdefault(row.section, []).append(row)

    # Sort within section: newest first
    for sec, items in grouped.items():
        items.sort(key=lambda x: (x.end_year, x.start_year, x.venue_full, x.venue, x.role), reverse=True)

    # Render sections
    out = []
    for section, items in grouped.items():
        if not section:
            continue
        out.append("    <section>")
        out.append(f"      <h2>{html.escape(section)}</h2>")
        out.append("      <ul>")
        for item in items:
            out.append(f"        {_format_li(item)}")
        out.append("      </ul>")
        out.append("    </section>")
        out.append("")  # blank line between sections
    return "\n".join(out).rstrip() + "\n"


def inject(raw_html: str, replacement: str) -> str:
    if START_MARKER not in raw_html or END_MARKER not in raw_html:
        raise ValueError("Could not find SERVICE markers in service_raw.html")

    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        flags=re.DOTALL,
    )
    block = f"{START_MARKER}\n{replacement}    {END_MARKER}"
    return pattern.sub(block, raw_html, count=1)


def main() -> None:
    rows = read_rows(CSV_PATH)
    replacement = build_service_html(rows)
    raw = RAW_HTML_PATH.read_text(encoding="utf-8")
    final = inject(raw, replacement)
    OUT_HTML_PATH.write_text(final, encoding="utf-8")
    print(f"Wrote {OUT_HTML_PATH}")


if __name__ == "__main__":
    main()