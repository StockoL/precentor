"""
Reading a Google Sheet as the import's CSV, from a link the person pastes.

The server never fetches the address that was typed. It takes the
spreadsheet's ID, and the tab's if there is one, out of the link with a
strict pattern and builds Google's own CSV export address from them, so
a link can't point the server anywhere else. The sheet has to be shared
as "anyone with the link can view": otherwise Google answers with its
sign-in page, which is HTML, not CSV, and the person is told so.
"""

import re
import urllib.error
import urllib.request

from .importing import MAX_BYTES, ImportProblem

SHEET = re.compile(r"^https://docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]{20,100})(?:[/?#].*)?$")
TAB = re.compile(r"[#?&]gid=(\d{1,12})\b")
EXPORT = "https://docs.google.com/spreadsheets/d/{id}/export?format=csv"
TIMEOUT_SECONDS = 10


def export_address(link):
    """The CSV export address for a Google Sheets link, or ImportProblem if
    it isn't one."""
    link = link.strip()
    sheet = SHEET.match(link)
    if not sheet:
        raise ImportProblem(
            "That isn't a Google Sheets link. Copy it from the address bar; it starts "
            "https://docs.google.com/spreadsheets/."
        )
    address = EXPORT.format(id=sheet.group(1))
    tab = TAB.search(link)
    return address + f"&gid={tab.group(1)}" if tab else address


def fetch_sheet(link):
    """The sheet's contents as CSV bytes, read no further than one byte past
    the import's size limit, as the file check reports a file that's too
    big."""
    request = urllib.request.Request(export_address(link), headers={"User-Agent": "Precentor"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403, 404):
            raise ImportProblem(not_shared()) from error
        raise ImportProblem("Google couldn't send the sheet just now. Try again in a minute.") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise ImportProblem("Google couldn't be reached just now. Try again in a minute.") from error
    if not content_type.startswith("text/csv"):
        raise ImportProblem(not_shared())
    return data


def not_shared():
    return (
        "Google didn't send the sheet, so either it isn't shared or the link is wrong. In Google Sheets "
        "choose Share, then under General access choose Anyone with the link, and copy the link again."
    )
