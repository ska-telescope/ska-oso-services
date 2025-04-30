import unittest

from flask import Response

from ska_oso_pht_services import set_default_headers_on_response


class TestDefaultHeaders(unittest.TestCase):
    def test_set_default_headers_on_response(self):
        response = Response()
        response = set_default_headers_on_response(response)
        self.assertIn("Access-Control-Allow-Origin", response.headers)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
