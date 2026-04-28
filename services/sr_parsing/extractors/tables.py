"""Extract HTML tables as list of list-of-dicts (EXTR-05)."""
from __future__ import annotations

from selectolax.parser import HTMLParser


def extract(tree: HTMLParser, url: str) -> dict:
    """Extract HTML tables. Returns list of dicts per table using header row as keys. Never raises."""
    try:
        table_nodes = tree.css("table")
        tables: list[list[dict[str, str]]] = []

        for table_node in table_nodes:
            headers: list[str] = []
            rows: list[list[str]] = []

            # Extract headers from <thead><tr><th> or first <tr> with <th>
            thead = table_node.css_first("thead")
            if thead:
                for th in thead.css("th"):
                    headers.append((th.text() or "").strip())

            # If no thead, check first tr for th elements
            all_trs = table_node.css("tr")
            if not headers and all_trs:
                first_tr = all_trs[0]
                ths = first_tr.css("th")
                if ths:
                    for th in ths:
                        headers.append((th.text() or "").strip())
                    all_trs = all_trs[1:]  # Skip header row

            # Extract data rows
            for tr in all_trs:
                tds = tr.css("td")
                if not tds:
                    continue
                row = [(td.text() or "").strip() for td in tds]
                rows.append(row)

            # Convert rows to list of dicts using headers
            table_dicts: list[dict[str, str]] = []
            if headers:
                for row in rows:
                    row_dict: dict[str, str] = {}
                    for i, val in enumerate(row):
                        key = headers[i] if i < len(headers) else f"col_{i}"
                        row_dict[key] = val
                    table_dicts.append(row_dict)
            else:
                # No headers -- use col_0, col_1, etc.
                for row in rows:
                    row_dict: dict[str, str] = {}
                    for i, val in enumerate(row):
                        row_dict[f"col_{i}"] = val
                    table_dicts.append(row_dict)

            tables.append(table_dicts)

        return {
            "table_count": len(tables),
            "tables": tables,
        }
    except Exception:
        return {"table_count": 0, "tables": []}
