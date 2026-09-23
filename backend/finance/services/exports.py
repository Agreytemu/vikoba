"""CSV export of ledger-derived reports.

Reports stay read-only: exporting never amends books; it only serialises the
already journal-derived statement/report rows into UTF-8 CSV (with a BOM so
Excel reads them unmangled).
"""
import csv
import io
import json

DEFAULT_HEADERS = [
    "account_number",
    "date",
    "reference",
    "transaction_type",
    "status",
    "description",
    "member",
    "amount",
    "delta",
    "running_balance",
]


def report_rows(report):
    """Pull flat rows out of a statement/report payload.

    Member savings statements nest per-account rows; other reports carry a flat
    ``rows`` key. The per-account membership is stamped onto each exported row.
    """
    rows = report.get("rows")
    if rows is not None:
        return rows
    if "accounts" in report:
        flattened = []
        for account in report["accounts"]:
            for row in account.get("rows", []):
                stamped = dict(row)
                stamped["account_number"] = account["account_number"]
                flattened.append(stamped)
        return flattened
    return []


def rows_to_csv(rows, headers=None):
    """Flatten dict rows into CSV text (UTF-8 BOM, CRLF)."""
    if not rows:
        headers = headers or []
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\r\n")
        writer.writerow(headers)
        return "\ufeff" + buf.getvalue()

    selected = headers or DEFAULT_HEADERS
    keys = [key for key in selected if key in rows[0]] or list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(keys)
    for row in rows:
        writer.writerow([_csv_cell(row.get(key)) for key in keys])
    return "\ufeff" + buf.getvalue()


def report_to_csv(report, headers=None):
    """CSV text for any statement/report payload."""
    return rows_to_csv(report_rows(report), headers=headers)


def _csv_cell(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return value