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


class SavingTests(TestCase):
    def setUp(self):
        from accounts.testing import make_organisation, make_user

        self.church = make_organisation()
        self.user = make_user("librarian", organisation=self.church)

    def save(self, *lines):
        from .importing import check_file, save_import

        return save_import(check_file(csv_bytes(*lines), self.church), self.church, self.user, "library.csv")

    def test_good_rows_are_saved_together_as_one_pending_import(self):
        batch = self.save("Title,Composer surname,Voicing", "Ave verum,Byrd,SATB", ",Tallis,", "Locus iste,Bruckner,")
        self.assertTrue(batch.is_pending)
        self.assertEqual((batch.created_by, batch.original_filename), (self.user, "library.csv"))
        self.assertEqual(sorted(batch.scores.values_list("title", flat=True)), ["Ave verum", "Locus iste"])
        self.assertEqual(batch.report["imported"], 2)
        self.assertEqual(batch.report["skipped"], [[3, "no title"]])

    def test_likely_duplicates_are_noted_not_refused(self):
        from precentor_project.testing import make_score

        make_score(organisation=self.church, title="Ave Verum", composer_surname="BYRD")
        batch = self.save("Title,Composer surname", "ave verum,byrd", "Locus iste,Bruckner")
        self.assertEqual(batch.scores.count(), 2)
        self.assertEqual(batch.report["duplicates"], ["ave verum (byrd)"])

    def test_another_churchs_scores_dont_count_as_duplicates(self):
        from accounts.testing import make_organisation
        from precentor_project.testing import make_score

        make_score(organisation=make_organisation("St Elsewhere"), title="Ave verum", composer_surname="Byrd")
        self.assertEqual(self.save("Title,Composer surname", "Ave verum,Byrd").report["duplicates"], [])

    def test_the_encoding_and_ignored_columns_are_reported(self):
        from .importing import check_file, save_import

        data = csv_bytes("Title,Composer surname,Shelf mark", "Ave,Duruflé,3", encoding="cp1252")
        batch = save_import(check_file(data, self.church), self.church, self.user, "old.csv")
        self.assertTrue(batch.report["read_as_windows_1252"])
        self.assertEqual(batch.report["ignored_columns"], ["Shelf mark"])

    def test_nothing_is_saved_if_writing_the_scores_fails(self):
        from unittest import mock

        from .models import Score, ScoreImport

        with mock.patch.object(Score.objects, "bulk_create", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.save("Title,Composer surname", "Ave verum,Byrd")
        self.assertFalse(ScoreImport.objects.exists())

    def test_a_file_with_no_usable_rows_makes_no_import(self):
        from .models import ScoreImport

        with self.assertRaises(ValueError):
            self.save("Title,Composer surname", ",Byrd")
        self.assertFalse(ScoreImport.objects.exists())


class ImportPagesTests(TestCase):
    def setUp(self):
        from accounts.testing import make_organisation, make_user

        self.church = make_organisation()
        self.librarian = make_user("librarian", organisation=self.church)
        self.client.force_login(self.librarian)

    def upload(self, *lines, name="library.csv"):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return self.client.post("/library/import/", {"file": SimpleUploadedFile(name, csv_bytes(*lines))}, follow=True)

    def test_the_template_has_every_header_and_opens_in_excel(self):
        from .importing import COLUMNS

        response = self.client.get("/library/import/template/")
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment", response["Content-Disposition"])
        text = response.content.decode("utf-8")
        self.assertTrue(text.startswith("\ufeff"))
        self.assertEqual(text.lstrip("\ufeff").strip(), ",".join(header for header, _, _ in COLUMNS))

    def test_the_page_explains_the_format_with_an_example(self):
        response = self.client.get("/library/import/")
        self.assertContains(response, "Download the template")
        self.assertContains(response, "Title (needed)")
        self.assertContains(response, "Rorate caeli")
        self.assertContains(response, 'enctype="multipart/form-data"')

    def test_importing_shows_what_happened(self):
        response = self.upload(
            "Title,Composer surname,Voicing,Shelf mark", "Ave verum,Byrd,SATB,3", ",Tallis,,", "Locus iste,Bruckner,,"
        )
        self.assertContains(response, "2 scores imported from library.csv")
        self.assertContains(response, "Row 3: no title")
        self.assertContains(response, "Shelf mark")
        self.assertContains(response, "1 of them has no voicing yet")
        self.assertContains(response, "?voicing=unspecified")

    def test_a_file_that_cant_work_comes_back_with_the_reason(self):
        from .models import ScoreImport

        response = self.upload("Title,Voicing", "Ave,SATB")
        self.assertContains(response, "no Composer surname column")
        response = self.upload("Title,Composer surname", ",Byrd")
        self.assertContains(response, "None of the rows could be imported (row 2: no title)")
        self.assertFalse(ScoreImport.objects.exists())

    def test_viewers_cant_import_and_another_churchs_import_isnt_found(self):
        from accounts.testing import make_organisation, make_user

        from .models import ScoreImport

        theirs = ScoreImport.objects.create(organisation=make_organisation("St Elsewhere"), original_filename="x.csv")
        self.assertEqual(self.client.get(f"/library/import/{theirs.pk}/").status_code, 404)
        self.client.force_login(make_user("viewer", organisation=self.church))
        for url in ("/library/import/", "/library/import/template/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)


class KeepImportTests(TestCase):
    def setUp(self):
        from accounts.testing import make_organisation, make_user

        from .importing import check_file, save_import

        self.church = make_organisation()
        user = make_user("librarian", organisation=self.church)
        self.client.force_login(user)
        checked = check_file(csv_bytes("Title,Composer surname", "Ave verum,Byrd", "Locus iste,Bruckner"), self.church)
        self.batch = save_import(checked, self.church, user, "library.csv")
        self.url = f"/library/import/{self.batch.pk}/keep/"

    def test_the_result_page_offers_it_and_says_what_it_means(self):
        response = self.client.get(f"/library/import/{self.batch.pk}/")
        self.assertContains(response, f'action="{self.url}"')
        self.assertContains(response, "can't be removed as a whole")

    def test_keeping_closes_the_import_and_says_so(self):
        response = self.client.post(self.url, follow=True)
        self.assertRedirects(response, "/library/")
        self.assertContains(response, "Kept 2 scores from library.csv.")
        self.batch.refresh_from_db()
        self.assertFalse(self.batch.is_pending)
        self.assertContains(self.client.get(f"/library/import/{self.batch.pk}/"), "have been kept")

    def test_keeping_twice_or_by_get_or_as_a_viewer_does_nothing(self):
        from accounts.testing import make_user

        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.client.post(self.url)
        self.assertEqual(self.client.post(self.url).status_code, 404)
        self.client.force_login(make_user("viewer", organisation=self.church))
        self.assertEqual(self.client.post(self.url).status_code, 403)
