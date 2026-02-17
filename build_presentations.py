#!/usr/bin/env python3
"""
Generate presentations.html from presentations.csv + presentations_raw.html.

Rules:
- Dates: <time datetime="YYYY-MM">Mon YYYY</time> (no assumed day)
- Title italic: <em>...</em>
- Text:
    - If co-presenters: ", presented with X at the <venue>"
    - Else: ", presented at the <venue>"
- Add spans:
    <span class="copresenters">...</span>
    <span class="presentation-venue">...</span>
- Wrap acronyms (3+ consecutive uppercase letters) with <span class="sc">...</span>
"""

from __future__ import annotations

import csv
import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


CSV_PATH = Path("presentations.csv")
RAW_HTML_PATH = Path("presentations_raw.html")
OUT_HTML_PATH = Path("presentations.html")

START_MARKER = "<!-- PRESENTATION:START -->"
END_MARKER = "<!-- PRESENTATION:END -->"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

ACRONYM_RE = re.compile(r"\b[A-Z]{3,}\b")


@dataclass(frozen=True)
class PresentationRow:
    year: int
    month: int
    title: str
    copresenters: str
    venue: str


def _parse_mm_yyyy(s: str) -> Tuple[int, int]:
    s = s.strip()
    m = re.fullmatch(r"(\d{2})/(\d{2}|\d{4})", s)
    if not m:
        raise ValueError(f"Invalid date format (expected MM/YY or MM/YYYY): {s!r}")
    month = int(m.group(1))
    year_part = m.group(2)
    year = int(year_part)
    if len(year_part) == 2:
        year += 2000
    if not (1 <= month <= 12):
        raise ValueError(f"Invalid month in date: {s!r}")
    return year, month


def _time_tag(year: int, month: int) -> str:
    datetime_attr = f"{year:04d}-{month:02d}"
    label = f"{MONTHS[month - 1]} {year:04d}"
    return f'<time datetime="{datetime_attr}">{label}</time>'


def _escape_and_sc(text: str) -> str:
    escaped = html.escape(text)

    def repl(m: re.Match[str]) -> str:
        tok = m.group(0)
        return f'<span class="sc">{tok}</span>'

    return ACRONYM_RE.sub(repl, escaped)


def _read_rows(path: Path) -> list[PresentationRow]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=",")
        rows: list[PresentationRow] = []
        for r in reader:
            date_raw = (r.get("date") or "").strip()
            title = (r.get("title") or "").strip()
            cop = (r.get("co-presenters") or "").strip()
            venue = (r.get("venue") or "").strip()

            if not date_raw or not title or not venue:
                raise ValueError(f"Missing required field (date/title/venue) in row: {r}")

            year, month = _parse_mm_yyyy(date_raw)
            rows.append(PresentationRow(year=year, month=month, title=title, copresenters=cop, venue=venue))
    return rows


def _li(row: PresentationRow) -> str:
    title_html = f"<em>{_escape_and_sc(row.title)}</em>"

    cop = row.copresenters.strip()
    venue_html = _escape_and_sc(row.venue)

    # Always include both spans; venue span contains the entire trailing phrase
    if cop:
        cop_span = f'<span class="copresenters">, presented with {_escape_and_sc(cop)}</span>'
        venue_span = f'<span class="presentation-venue"> at the {venue_html}</span>'
    else:
        cop_span = '<span class="copresenters"></span>'
        venue_span = f'<span class="presentation-venue">, presented at the {venue_html}</span>'

    return (
        "    <li>\n"
        f"      {_time_tag(row.year, row.month)}\n"
        '      <span class="presentation-text">\n'
        f"        {title_html}{cop_span}{venue_span}\n"
        "      </span>\n"
        "    </li>"
    )


def build_presentations_html(rows: list[PresentationRow]) -> str:
    rows_sorted = sorted(rows, key=lambda r: (r.year, r.month), reverse=True)

    out = []
    out.append('  <ul class="content-list presentations">')
    out.append("")
    for row in rows_sorted:
        out.append(_li(row))
        out.append("")
    out.append("  </ul>")
    return "\n".join(out) + "\n"


def inject(raw_html: str, replacement: str) -> str:
    if START_MARKER not in raw_html or END_MARKER not in raw_html:
        raise ValueError("Could not find PRESENTATION markers in presentations_raw.html")

    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        flags=re.DOTALL,
    )
    block = f"{START_MARKER}\n{replacement}    {END_MARKER}"
    return pattern.sub(block, raw_html, count=1)


def main() -> None:
    rows = _read_rows(CSV_PATH)
    replacement = build_presentations_html(rows)

    raw = RAW_HTML_PATH.read_text(encoding="utf-8")
    final = inject(raw, replacement)

    OUT_HTML_PATH.write_text(final, encoding="utf-8")
    print(f"Wrote {OUT_HTML_PATH}")


if __name__ == "__main__":
    main()