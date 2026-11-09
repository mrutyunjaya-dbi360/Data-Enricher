from django.test import SimpleTestCase
from pipeline.helpers import is_blacklisted, normalize_domain


class PipelinePortTests(SimpleTestCase):
    def test_blacklist_linkedin(self):
        self.assertTrue(is_blacklisted("https://www.linkedin.com/company/foo"))

    def test_normalize(self):
        self.assertEqual(normalize_domain("example.com"), "https://example.com")
