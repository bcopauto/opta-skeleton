"""Detect comparison tables: 3+ cols with header keywords like vs, feature, plan (EXTR-10)."""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser

_COMPARISON_KEYWORDS = re.compile(
    r"vs\.?|versus|feature|plan|pricing|compare|package|tier|basic|pro|enterprise|"
    r"free|premium|starter|standard|option|choice|select",
    re.I,
)


def extract(tree: HTMLParser, url: str) -> dict:
    """Detect comparison tables. A comparison table has 3+ cols and header keywords. Never raises."""
    try:
        comparison_tables: list[dict] = []

        for table in tree.css("table"):
            # Get headers
            headers: list[str] = []
            thead = table.css_first("thead")
            if thead:
                for th in thead.css("th"):
                    headers.append((th.text() or "").strip())

            if not headers:
                first_tr = table.css_first("tr")
                if first_tr:
                    for th in first_tr.css("th"):
                        headers.append((th.text() or "").strip())

            # Must have 3+ columns
            if len(headers) < 3:
                continue

            # Check if any header contains comparison keywords
            header_text = " ".join(headers).lower()
            if not _COMPARISON_KEYWORDS.search(header_text):
                continue

            # Extract table data
            all_trs = table.css("tr")
            rows: list[dict[str, str]] = []
            for tr in all_trs:
                tds = tr.css("td")
                if not tds:
                    continue
                row_dict: dict[str, str] = {}
                for i, td in enumerate(tds):
                    key = headers[i] if i < len(headers) else f"col_{i}"
                    row_dict[key] = (td.text() or "").strip()
                rows.append(row_dict)

            comparison_tables.append({
                "headers": headers,
                "row_count": len(rows),
                "rows": rows,
            })

        return {
            "has_comparison_table": len(comparison_tables) > 0,
            "comparison_table_count": len(comparison_tables),
            "comparison_tables": comparison_tables,
        }
    except Exception:
        return {"has_comparison_table": False, "comparison_table_count": 0, "comparison_tables": []}
