from django.test import TestCase

from accounts.testing import make_user


class BaseTemplateTests(TestCase):
    """Checks on templates/base.html, through the login page, which
    renders it without needing a signed-in user."""

    def setUp(self):
        self.response = self.client.get("/accounts/login/")

    def test_nav_is_labelled(self):
        self.assertContains(self.response, 'aria-label="Main"')

    def test_logged_out_nav_offers_only_log_in(self):
        # Every other page needs a login, so its link would only bounce
        # the visitor back here.
        for href in ("/library/", "/comments/inbox/", "/settings/"):
            with self.subTest(href=href):
                self.assertNotContains(self.response, f'href="{href}"')
        self.assertContains(self.response, 'href="/accounts/login/"')

    def test_viewport_meta_tag_present(self):
        # Without it, phones lay the page out at desktop width and zoom
        # out, so the fluid type scale and media queries never apply.
        self.assertContains(
            self.response,
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            html=True,
        )

    def test_skip_link_targets_main(self):
        self.assertContains(
            self.response,
            '<a class="skip-link" href="#main">Skip to main content</a>',
            html=True,
        )
        self.assertContains(self.response, '<main id="main"')

    def test_only_site_wide_scripts_load_everywhere(self):
        # Page scripts come through each page's extra_js block, so a page
        # without those features doesn't download them.
        for name in ("theme-choice.js", "user-menu.js", "toast.js"):
            with self.subTest(name=name):
                self.assertContains(self.response, f"src/js/{name}")
        for name in (
            "service-detail.js", "comments.js", "score-picker.js",
            "occasion-suggest.js", "crest-crop.js", "tag-input.js",
        ):
            with self.subTest(name=name):
                self.assertNotContains(self.response, f"src/js/{name}")


class NavWordingTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user("conductor"))

    def test_nav_links_and_page_headings_use_the_same_words(self):
        pages = {
            "/library/": "Library",
            "/comments/inbox/": "Inbox",
            "/settings/": "Settings",
        }
        for url, word in pages.items():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(
                    response, f'<a href="{url}" aria-current="page">{word}</a>', html=True
                )
                self.assertContains(response, f"<h1>{word}</h1>", html=True)
                self.assertContains(response, f"<title>{word} — Precentor</title>", html=True)


class NewAndEditWordingTests(TestCase):
    """Create pages and links say New; edit pages say Edit; the tab title
    matches the heading."""

    def setUp(self):
        from datetime import date

        from library.models import Score
        from planning.models import Service, Term

        self.client.force_login(make_user("conductor"))
        self.term = Term.objects.create(
            name="Lent 2027",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 3, 31),
            calendar_use="current",
        )
        self.service = Service.objects.create(
            term=self.term, date=date(2027, 1, 10), service_type="Sung Mass"
        )
        self.score = Score.objects.create(title="Ave verum", composer_surname="Byrd")

    def test_form_pages(self):
        from django.urls import reverse

        pages = [
            (reverse("planning:term_create"), "New term", "New term"),
            (reverse("planning:term_update", args=[self.term.pk]), "Edit term", "Edit term"),
            (reverse("planning:service_create", args=[self.term.pk]),
             "New service", "New service in Lent 2027"),
            (reverse("planning:service_update", args=[self.service.pk]),
             "Edit service", "Edit service"),
            (reverse("library:score_create"), "New score", "New score"),
            (reverse("library:score_update", args=[self.score.pk]), "Edit score", "Edit score"),
        ]
        for url, title, heading in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, f"<title>{title} — Precentor</title>", html=True)
                self.assertContains(response, f"<h1>{heading}</h1>", html=True)

    def test_create_links(self):
        for url, link in [
            ("/", ">New term</a>"),
            (self.term.get_absolute_url(), ">New service</a>"),
            ("/library/", ">New score</a>"),
        ]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, link)
                for retired in (">Add a term<", ">Add a service<", ">Add a score<"):
                    self.assertNotContains(response, retired)


class PrimaryActionTests(TestCase):
    """One filled primary button per view, at most; form pages have one."""

    # Same term, service and score as the wording tests, without
    # inheriting (and so rerunning) their test methods.
    setUp = NewAndEditWordingTests.setUp

    def test_at_most_one_primary_action_per_page(self):
        from django.urls import reverse

        forms = [
            reverse("planning:term_create"),
            reverse("planning:service_update", args=[self.service.pk]),
            reverse("library:score_update", args=[self.score.pk]),
            "/settings/",
        ]
        others = [
            "/",
            self.term.get_absolute_url(),
            self.service.get_absolute_url(),
            "/library/",
            self.score.get_absolute_url(),
            "/comments/inbox/",
        ]
        for url in forms + others:
            with self.subTest(url=url):
                count = self.client.get(url).content.decode().count('class="btn-primary"')
                if url in forms:
                    self.assertEqual(count, 1)
                else:
                    self.assertLessEqual(count, 1)

    def test_list_pages_put_their_new_action_in_the_page_header(self):
        for url, new in [("/", "/terms/add/"), ("/library/", "/library/add/")]:
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                header = html.split('<header class="page-header">', 1)[1].split("</header>", 1)[0]
                self.assertIn(f'<a class="btn-primary" href="{new}">', header)


class NavInboxCountTests(TestCase):
    def setUp(self):
        from datetime import date

        from planning.models import Term

        self.user = make_user("conductor")
        self.client.force_login(self.user)
        self.term = Term.objects.create(
            name="Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            calendar_use="current",
        )

    def test_count_shows_open_comments_only(self):
        from comments.models import Comment

        Comment.objects.create(author=self.user, body="Open", target=self.term)
        Comment.objects.create(author=self.user, body="Open too", target=self.term)
        Comment.objects.create(
            author=self.user, body="Closed", target=self.term, is_open=False
        )
        self.assertContains(
            self.client.get("/library/"),
            '<span class="nav-count">2<span class="visually-hidden"> open</span></span>',
            html=True,
        )

    def test_no_count_when_nothing_is_open(self):
        self.assertNotContains(self.client.get("/library/"), "nav-count")


class NavCurrentSectionTests(TestCase):
    setUp = NewAndEditWordingTests.setUp

    def test_landing_page_link_is_the_current_page(self):
        response = self.client.get("/")
        self.assertContains(response, '<a href="/" aria-current="page">Terms</a>', html=True)
        self.assertContains(response, '<a href="/library/">Library</a>', html=True)

    def test_page_inside_a_section_marks_that_section(self):
        # A service page belongs to Terms without being the Terms page.
        response = self.client.get(self.service.get_absolute_url())
        self.assertContains(response, '<a href="/" aria-current="true">Terms</a>', html=True)
        response = self.client.get(self.score.get_absolute_url())
        self.assertContains(
            response, '<a href="/library/" aria-current="true">Library</a>', html=True
        )


class UserMenuTests(TestCase):
    def test_menu_holds_appearance_settings_and_log_out(self):
        self.client.force_login(make_user("conductor", email="louis@example.com"))
        html = self.client.get("/").content.decode()
        menu = html.split('<details class="user-menu">', 1)[1].split("</details>", 1)[0]
        self.assertIn("<summary>louis@example.com</summary>", menu)
        # Hidden in the HTML: the script reveals it, since it needs JS.
        self.assertIn('<fieldset id="theme-choice" class="theme-choice" hidden>', menu)
        self.assertIn('href="/settings/"', menu)
        self.assertIn(">Log out</button>", menu)
        self.assertNotIn('id="theme-toggle"', html)


class NavSettingsLinkTests(TestCase):
    """Settings is conductor-only, so the link shows only to conductors."""

    def test_conductor_sees_settings_link(self):
        self.client.force_login(make_user("conductor"))
        self.assertContains(self.client.get("/library/"), 'href="/settings/"')

    def test_librarian_does_not_see_settings_link(self):
        self.client.force_login(make_user("librarian"))
        self.assertNotContains(self.client.get("/library/"), 'href="/settings/"')
