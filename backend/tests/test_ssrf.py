from django.test import SimpleTestCase
from datasources.ssrf import assert_public_mongo_uri, SSRFBlocked


class SSRFTests(SimpleTestCase):
    def test_blocks_localhost(self):
        with self.assertRaises(SSRFBlocked):
            assert_public_mongo_uri("mongodb://127.0.0.1:27017/db")

    def test_blocks_private(self):
        with self.assertRaises(SSRFBlocked):
            assert_public_mongo_uri("mongodb://10.0.0.1:27017/db")

    def test_blocks_metadata(self):
        with self.assertRaises(SSRFBlocked):
            assert_public_mongo_uri("mongodb://169.254.169.254/db")
