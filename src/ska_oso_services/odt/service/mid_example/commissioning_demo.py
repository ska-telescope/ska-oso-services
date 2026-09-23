import json

from ska_oso_pdm import SBDefinition
from ska_oso_services.odt.service.mid_example.sbd_generator import generate_mid_commissioning_five_point_sbd
from temptokens import *
import requests
from ska_oso_pdm.builders import MidSBDefinitionBuilder, populate_scan_sequences

OSO_SERVICES_URL = "https://k8s.stfc.skao.int/staging-oso-cloud/oso/api/v16"
OST_SERVICES_URL = "https://k8s.stfc.skao.int/staging-oso-mid/ost/api/v2"

# Copy your PRJ + OB HERE
PROJECT_ID = "prj-19qrcpp9kwh5"
OBSERVING_BLOCK_ID = "ob-19qrcpp9kxhn"

def get_headers(access_token) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }


# BUILD AN SBD AND SAVE TO THE ODA

TARGETS = ["PKS 0408-65", "PKS 1934-63"] # this could come from an input file or API input, either as

# Could generate one or more SBDs here
sbd = generate_mid_commissioning_five_point_sbd(TARGETS, sbd_name="Another Live Mid Demo example")

result = requests.post(f"{OSO_SERVICES_URL}/odt/prjs/{PROJECT_ID}/{OBSERVING_BLOCK_ID}/sbds", json=sbd.model_dump(mode="json"), headers=get_headers(OSO_SERVICES_TOKEN))

print(result.json())

sbd_id = result.json()["sbd"]["sbd_id"]

# ADD TO OBSERVING QUEUE
# This is used to execute SBDs at specific start times. Alternatively could just let the scheduler decide when
# to execute based on SBD (i.e. based on source visibility, resources availability and SBD constraints)

QUEUE_ID = "obsq-10r3antb2dkz" # need to query this from the OST
queue_item = {
  "items": [
    {
      "sbd_fk": sbd_id,
      "queue_fk": QUEUE_ID,
      "is_executed": False,
      "sbd_version": 1,
      "subarray_id": 1,
      "observation_start_time": "2026-09-22T14:54:12.517Z",
      "observation_end_time": "2026-09-22T14:56:12.517Z",
      "sbd_duration_min": 2,
      "window_period_min": 1
    }
  ],
  "is_active": True,
  "create_env": True
}

ost_result = requests.post(f"https://k8s.stfc.skao.int/dev-ska-oso-ost-services-thad-test/ost/api/v2/observing_queue/subarray/", headers=get_headers(OST_SERVICES_TOKEN))

print(ost_result.status_code)
print(ost_result.text)