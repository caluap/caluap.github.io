#!/usr/bin/env python3
"""
Generate service.html from service.csv + service_raw.html.

- Input:  service.csv (comma-delimited)
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
    show_org: bool
    venue_full: str
    organization: str
    start_year: int
    end_year: int


def _parse_bool(s: str) -> bool:
    return s.strip().lower() in {"true", "1", "yes", "y"}


def _year_range(start: int, end: int) -> str:
    return f"{start}" if start == end else f"{start}\u2013{end}"  # en-dash


ACRONYM_RE = re.compile(r"\b[A-Z]{3,}\b")


def _esc_sc_acronyms(text: str) -> str:
    """
    Escape HTML, then wrap 3+ letter ALL-CAPS tokens in <span class="sc">...</span>.
    Example: "ACM SIGACCESS Conference" -> "<span class='sc'>ACM</span> <span class='sc'>SIGACCESS</span> Conference"
    """
    s = html.escape(text)
    return ACRONYM_RE.sub(lambda m: f'<span class="sc">{m.group(0)}</span>', s)


def _sc(text: str) -> str:
    """Small-caps span with HTML escaping."""
    return f'<span class="sc">{html.escape(text)}</span>'


def _em(text: str) -> str:
    """Italic with acronym small-caps + HTML escaping."""
    return f"<em>{_esc_sc_acronyms(text)}</em>"


def _format_li(row: ServiceRow) -> str:
    section = row.section.strip()
    role = row.role.strip()
    venue = row.venue.strip()
    track = row.track.strip()
    venue_full = row.venue_full.strip()
    org = row.organization.strip()
    years = _year_range(row.start_year, row.end_year)

    # If show_year is True, show "(2023–2026)" style after the italicized journal title.
    year_suffix = f"&nbsp;({years})" if row.show_year else ""

    # For conference-like items (show_year=False), show a "(<SC VENUE ...>)" block.
    venue_year_block = ""
    if not row.show_year:
        base = re.split(r"[;,(]", venue)[0].strip()

        # If venue already contains a year, preserve it exactly.
        if re.search(r"\b\d{4}\b", base):
            label = base
        else:
            label = f"{base} {years}"

        venue_year_block = f" ({_sc(label.replace(' ', '\u00a0'))})"

    # Decide whether to show org at all (new column)
    org_out = org if row.show_org else ""

    # If venue_full already starts with org, don't print org separately (even if show_org=True)
    if org_out and venue_full and venue_full.lower().startswith(org_out.lower()):
        org_out = ""

    if section == "Conference Organization":
        if track:
            head = ", ".join([_esc_sc_acronyms(role), _esc_sc_acronyms(track)]) if role else _esc_sc_acronyms(track)

            tail_parts: list[str] = []
            if org_out:
                tail_parts.append(_sc(org_out))
            if venue_full:
                tail_parts.append(_esc_sc_acronyms(venue_full))
            tail = " ".join(tail_parts).strip()

            # If tail is empty for some reason, fall back to venue
            if not tail:
                tail = _esc_sc_acronyms(venue)

            return f"<li>{head}, {tail}{venue_year_block}</li>"

        parts: list[str] = []
        if role:
            parts.append(_esc_sc_acronyms(role))
        if org_out:
            parts.append(_sc(org_out))
        if venue_full:
            parts.append(_esc_sc_acronyms(venue_full))
        if not parts and venue:
            parts.append(_esc_sc_acronyms(venue))

        return f"<li>{', '.join(parts)}{venue_year_block}</li>"

    if section == "Peer Review":
        # Journal-ish: keep your "Reviewer, <em>Journal</em> (Year)" pattern
        is_journalish = bool(venue_full) and ("conference" not in venue_full.lower())

        if is_journalish and row.show_year:
            prefix = _esc_sc_acronyms(role) if role else "Reviewer"
            return f"<li>{prefix}, {_em(venue_full)}{year_suffix}</li>"

        # Conference-style reviewing:
        prefix = _esc_sc_acronyms(role) if role else "Reviewer"
        if track and not role:
            prefix = _esc_sc_acronyms(track)

        tail_parts: list[str] = []
        if org_out:
            tail_parts.append(_sc(org_out))
        if venue_full:
            tail_parts.append(_esc_sc_acronyms(venue_full))
        elif org:
            # If venue_full missing, at least show org (even if show_org=False, org here is raw fallback)
            tail_parts.append(_esc_sc_acronyms(org))
        elif venue:
            tail_parts.append(_esc_sc_acronyms(venue))

        tail = " ".join(tail_parts).strip()
        return f"<li>{prefix}, {tail}{venue_year_block}</li>"

    # Default for other sections (e.g., Community & Professional Service)
    role_txt = _esc_sc_acronyms(role) if role else ""
    venue_full_txt = _esc_sc_acronyms(venue_full) if venue_full else ""
    venue_sc = _sc(venue) if venue else ""
    org_txt = _esc_sc_acronyms(org) if org else ""

    chunks: list[str] = []
    if role_txt:
        chunks.append(role_txt)
    if venue_full_txt:
        chunks.append(venue_full_txt)
    if venue_sc:
        chunks.append(f"({venue_sc})")
    # In this “default” bucket, org is historically useful, so show it regardless of show_org.
    # If you want it controlled too, replace org_txt with ( _esc_sc_acronyms(org_out) if org_out else "" )
    if org_txt:
        chunks.append(org_txt)
    if years:
        chunks.append(f"({years})")

    return f"<li>{', '.join(chunks)}</li>"


def read_rows(path: Path) -> list[ServiceRow]:
    text = path.read_text(encoding="utf-8")
    reader = csv.DictReader(text.splitlines(), delimiter=",")

    rows: list[ServiceRow] = []
    for r in reader:
        rows.append(
            ServiceRow(
                section=(r.get("section") or "").strip(),
                role=(r.get("role") or "").strip(),
                venue=(r.get("venue") or "").strip(),
                track=(r.get("track") or "").strip(),
                show_year=_parse_bool(r.get("show_year") or "false"),
                show_org=_parse_bool(r.get("show_org") or "false"),
                venue_full=(r.get("venue_full") or "").strip(),
                organization=(r.get("organization") or "").strip(),
                start_year=int((r.get("start_year") or "0").strip() or "0"),
                end_year=int((r.get("end_year") or "0").strip() or "0"),
            )
        )
    return rows


def build_service_html(rows: list[ServiceRow]) -> str:
    grouped: "OrderedDict[str, list[ServiceRow]]" = OrderedDict()
    for row in rows:
        grouped.setdefault(row.section, []).append(row)

    # Sort within section: newest first
    for _, items in grouped.items():
        items.sort(key=lambda x: (x.end_year, x.start_year, x.venue_full, x.venue, x.role), reverse=True)

    out: list[str] = []
    for section, items in grouped.items():
        if not section:
            continue
        out.append("    <section>")
        out.append(f"      <h2>{_esc_sc_acronyms(section)}</h2>")
        out.append("      <ul>")
        for item in items:
            out.append(f"        {_format_li(item)}")
        out.append("      </ul>")
        out.append("    </section>")
        out.append("")
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