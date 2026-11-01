import io
import urllib.error
from unittest import mock

from django.test import SimpleTestCase

from .importing import MAX_BYTES, ImportProblem
from .sheets import export_address, fetch_sheet

SHEET_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz_0123456789-ab"
LINK = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit?usp=sharing"


class FakeResponse(io.BytesIO):
    def __init__(self, data, content_type):
        super().__init__(data)
        self.headers = {"Content-Type": content_type}


class ExportAddressTests(SimpleTestCase):
    def test_the_address_is_built_from_the_id(self):
        self.assertEqual(
            export_address(LINK), f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
        )

    def test_a_tab_is_kept(self):
        link = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid=42"
        self.assertTrue(export_address(link).endswith("&gid=42"))

    def test_anything_else_is_refused(self):
        for link in [
            "https://example.com/spreadsheets/d/" + SHEET_ID,
            "http://docs.google.com/spreadsheets/d/" + SHEET_ID,
            "https://docs.google.com.example.com/spreadsheets/d/" + SHEET_ID,
            "https://docs.google.com/document/d/" + SHEET_ID,
            "https://docs.google.com/spreadsheets/d/short",
        ]:
            with self.subTest(link=link), self.assertRaisesMessage(ImportProblem, "isn't a Google Sheets link"):
                export_address(link)


@mock.patch("library.sheets.urllib.request.urlopen")
class FetchSheetTests(SimpleTestCase):
    def test_returns_the_csv(self, urlopen):
        urlopen.return_value = FakeResponse(b"Title,Composer surname\r\n", "text/csv; charset=utf-8")
        self.assertEqual(fetch_sheet(LINK), b"Title,Composer surname\r\n")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, export_address(LINK))
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 10)

    def test_reads_no_more_than_one_byte_past_the_limit(self, urlopen):
        urlopen.return_value = FakeResponse(b"x" * (MAX_BYTES + 100), "text/csv")
        self.assertEqual(len(fetch_sheet(LINK)), MAX_BYTES + 1)

    def test_a_sign_in_page_means_not_shared(self, urlopen):
        urlopen.return_value = FakeResponse(b"<html>Sign in</html>", "text/html; charset=utf-8")
        with self.assertRaisesMessage(ImportProblem, "isn't shared"):
            fetch_sheet(LINK)

    def test_refused_or_missing_means_not_shared(self, urlopen):
        urlopen.side_effect = urllib.error.HTTPError(LINK, 404, "Not Found", {}, None)
        with self.assertRaisesMessage(ImportProblem, "isn't shared"):
            fetch_sheet(LINK)

    def test_no_connection(self, urlopen):
        urlopen.side_effect = urllib.error.URLError("no route")
        with self.assertRaisesMessage(ImportProblem, "couldn't be reached"):
            fetch_sheet(LINK)
