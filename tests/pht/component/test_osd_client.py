import json
import unittest
from http import HTTPStatus
from os import getenv

import requests

from tests.unit.util import VALID_OSD_GET_OSD_CYCLE1_RESULT_JSON, assert_json_is_equal

KUBE_NAMESPACE = getenv("KUBE_NAMESPACE", "ska-oso-pht-services")
OSD_API_URL = getenv(
    "OSD_API_URL",
    f"http://ska-ost-osd-rest-test:5000/{KUBE_NAMESPACE}/osd/api/v1",
)
OSD_ENDPOINT = "osd"


class TestOSDCLIENT(unittest.TestCase):
    def test_get_osd(self):
        cycle_id = 1
        response = requests.get(f"{OSD_API_URL}/{OSD_ENDPOINT}?cycle_id={cycle_id}")
        assert response.status_code == HTTPStatus.OK

        response_content = response.content.decode("utf-8")
        result = json.loads(response_content)
        expected_json = json.loads(VALID_OSD_GET_OSD_CYCLE1_RESULT_JSON)
        assert_json_is_equal(json.dumps(result), json.dumps(expected_json))

    def test_get_osd_unvalid_cycle(self):
        cycle_id = "dhfjdhfjdhfjd"
        response = requests.get(f"{OSD_API_URL}/{OSD_ENDPOINT}?cycle_id={cycle_id}")
        assert response.status_code == HTTPStatus.BAD_REQUEST
