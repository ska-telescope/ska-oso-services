"""
This script is an example of building one or many SBDefinitions from
a reduced set of inputs, and persisting those in the ODA for execution.

At the end of this script, you should be able to see the created SBDs
at {BASE_URL}/{PROJECT_ID}/{OBSERVING_BLOCK_ID}
"""

from datetime import datetime, timedelta

import requests
from astropy.time import Time
from temptokens import *

from ska_oso_services.odt.service.calibrator_sweep_sbd_generator import generate_cal_sweep_sbd

BASE_URL = "https://k8s.stfc.skao.int/staging-oso-cloud"
OSO_SERVICES_URL = f"{BASE_URL}/oso/api/v17"

PROJECT_ID = "prj-19qrcpp9kwh5"
OBSERVING_BLOCK_ID = "ob-1daazjn1d928"

EXAMPLE_START_TIME = datetime(2026, 10, 16, 16, 30)
DURATION = timedelta(minutes=30)

# SBD generation from a set of useful inputs
# Depending on the use case, the generator might return multiple SBDs, or you could
# loop over inputs multiple times. There is flexibility to make the inputs and generator
# as complex as you want.
# See https://gitlab.com/ska-telescope/oso/ska-oso-services/-/tree/mid-commissioning/src/ska_oso_services/odt/service?ref_type=heads
# for more inspiration

# This reuses the existing generator that is exposed in the UI
sbd = generate_cal_sweep_sbd(
    Time(EXAMPLE_START_TIME),
    duration=DURATION,
    primary_dwell=timedelta(minutes=5),
    secondary_dwell=None,
    interleave_primary=False,
    coarse_channel_start=206,
    coarse_channel_bandwidth=16,
    stations=[345],
    pst_mode=False,
)
sbd_id = mint_skuid('sbd')
sbd.sbd_id = sbd_id

# Note: if these SBDs are to be scheduled via the engine, you might want to set observing_constraints in the SBD

# Persist the SBDs in the ODA
response = requests.post(
    f"{OSO_SERVICES_URL}/odt/prjs/{PROJECT_ID}/{OBSERVING_BLOCK_ID}/sbds",
    json=sbd.model_dump(mode="json"),
    headers=get_headers(OSO_SERVICES_TOKEN),
)

# NOTE: if a specific generator is useful, we can expose it as a specific API like
# f"{OSO_SERVICES_URL}/odt/prjs/{PROJECT_ID}/{OBSERVING_BLOCK_ID}/generateGSMSurveySBDefinitions"
# that already exists.

if response.status_code != 200:
    print("Error to handle!")
    print(response.status_code)
    print(response.text)

if "Sign in" in response.text or "Microsoft" in response.text:
    print("Response was the login page - the token isn't being recognised by the oauth2 proxy")

print("SBD created")
print(response.json())

# Alternatively can import the skuid library and mint an SBD skuid before saving it, rather than letting
# the API handle the minting
sbd_id = response.json()["sbd"]["sbd_id"]
print("SBD ID")
print(sbd_id)
