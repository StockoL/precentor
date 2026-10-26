from django.test import SimpleTestCase, TestCase

from .importing import MAX_BYTES, MAX_ROWS, ImportProblem, read_rows


def csv_bytes(*lines, encoding="utf-8"):
    return "\r\n".join(lines).encode(encoding)


class ReadingTheFileTests(SimpleTestCase):
    def test_rows_come_back_keyed_by_field_with_spreadsheet_row_numbers(self):
        data = csv_bytes("Title,Composer surname", "Ave verum,Byrd", "If ye love me,Tallis")
        rows, fallback, ignored = read_rows(data)
        self.assertEqual(rows, [
            (2, {"title": "Ave verum", "composer_surname": "Byrd"}),
            (3, {"title": "If ye love me", "composer_surname": "Tallis"}),
        ])
        self.assertEqual((fallback, ignored), (False, []))

    def test_headers_match_in_any_order_case_and_spacing(self):
        rows, _, _ = read_rows(csv_bytes("  composer   SURNAME ,TITLE,voicing", "Byrd,Ave verum,SATB"))
        self.assertEqual(rows[0][1], {"composer_surname": "Byrd", "title": "Ave verum", "voicing": "SATB"})

    def test_semicolons_and_tabs_work_as_well_as_commas(self):
        for separator in (";", "\t"):
            with self.subTest(separator=repr(separator)):
                rows, _, _ = read_rows(csv_bytes(f"Title{separator}Composer surname", f"Ave, verum{separator}Byrd"))
                self.assertEqual(rows[0][1]["title"], "Ave, verum")

    def test_excels_byte_order_mark_is_dropped(self):
        rows, fallback, _ = read_rows(b"\xef\xbb\xbf" + csv_bytes("Title,Composer surname", "Ave,Byrd"))
        self.assertEqual(rows[0][1]["title"], "Ave")
        self.assertFalse(fallback)

    def test_older_excels_encoding_is_read_and_noted(self):
        rows, fallback, _ = read_rows(csv_bytes("Title,Composer surname", "Ave,Duruflé", encoding="cp1252"))
        self.assertEqual(rows[0][1]["composer_surname"], "Duruflé")
        self.assertTrue(fallback)

    def test_quoted_cells_and_blank_rows(self):
        data = csv_bytes("Title,Composer surname", '"Ave, verum corpus",Byrd', ",", "", "Locus iste,Bruckner")
        rows, _, _ = read_rows(data)
        self.assertEqual([number for number, _ in rows], [2, 5])
        self.assertEqual(rows[0][1]["title"], "Ave, verum corpus")

    def test_short_rows_are_padded_and_extra_columns_noted(self):
        rows, _, ignored = read_rows(csv_bytes("Title,Composer surname,Voicing,Shelf mark", "Ave,Byrd"))
        self.assertEqual(rows[0][1]["voicing"], "")
        self.assertEqual(ignored, ["Shelf mark"])

    def test_a_missing_required_column_stops_the_import_and_names_it(self):
        with self.assertRaisesMessage(ImportProblem, "no Composer surname column"):
            read_rows(csv_bytes("Title,Voicing", "Ave,SATB"))

    def test_an_empty_file_stops_the_import(self):
        for data in (b"", b"\r\n"):
            with self.subTest(data=data), self.assertRaisesMessage(ImportProblem, "empty"):
                read_rows(data)

    def test_the_size_and_row_limits(self):
        with self.assertRaisesMessage(ImportProblem, "larger than 2 MB"):
            read_rows(b"x" * (MAX_BYTES + 1))
        too_many = csv_bytes("Title,Composer surname", *(["Ave,Byrd"] * (MAX_ROWS + 1)))
        with self.assertRaisesMessage(ImportProblem, "more than 5,000 scores"):
            read_rows(too_many)


class CheckingRowsTests(TestCase):
    def check(self, *lines):
        from accounts.testing import make_organisation

        from .importing import check_file

        return check_file(csv_bytes(*lines), make_organisation())

    def test_good_rows_become_unsaved_scores_for_the_church(self):
        from .models import Score

        checked = self.check(
            "Title,Composer surname,Voicing,Language,Copies owned,Duration (minutes),Last sung",
            "Ave verum,Byrd,SATB,Latin,24,4,2026-03-15",
        )
        score = checked.scores[0]
        self.assertEqual((score.title, score.copies_owned, score.duration_minutes), ("Ave verum", 24, 4))
        self.assertEqual(str(score.last_sung_manual), "2026-03-15")
        self.assertIsNone(score.pk)
        self.assertEqual(score.organisation.name, "Test Church")
        self.assertFalse(Score.objects.exists())

    def test_only_title_and_composer_are_needed(self):
        checked = self.check("Title,Composer surname,Voicing,Copies owned", "Ave verum,Byrd,,")
        score = checked.scores[0]
        self.assertEqual((score.voicing, score.copies_owned), ("", 0))

    def test_dates_either_way_round(self):
        checked = self.check("Title,Composer surname,Last sung", "A,Byrd,15/03/2026", "B,Byrd,2026-03-15")
        self.assertEqual({str(score.last_sung_manual) for score in checked.scores}, {"2026-03-15"})

    def test_bad_rows_are_skipped_with_their_row_number_and_a_plain_reason(self):
        checked = self.check(
            "Title,Composer surname,Copies owned,Last sung",
            ",Byrd,,",
            "Ave,Byrd,lots,",
            "Ave,Byrd,,next week",
            "Locus iste,Bruckner,,",
        )
        self.assertEqual([score.title for score in checked.scores], ["Locus iste"])
        self.assertEqual([number for number, _ in checked.skipped], [2, 3, 4])
        self.assertEqual(checked.skipped[0][1], "no title")
        self.assertIn("Copies owned:", checked.skipped[1][1])
        self.assertIn("Last sung: write it as 2026-03-15 or 15/03/2026", checked.skipped[2][1])

    def test_an_over_long_value_is_skipped(self):
        checked = self.check("Title,Composer surname", f"{'x' * 201},Byrd")
        self.assertIn("Title:", checked.skipped[0][1])

    def test_part_counts_come_from_a_plain_voicing(self):
        checked = self.check(
            "Title,Composer surname,Voicing", "A,Byrd,SSATB", "B,Byrd,SATB.SATB", "C,Byrd,Unison", "D,Byrd,"
        )
        counts = [(s.soprano_parts, s.alto_parts, s.tenor_parts, s.bass_parts) for s in checked.scores]
        self.assertEqual(counts, [(2, 1, 1, 1), (2, 2, 2, 2), (0, 0, 0, 0), (0, 0, 0, 0)])
