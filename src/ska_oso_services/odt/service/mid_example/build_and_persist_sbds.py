"""
This script is an example of building one or many SBDefinitions from
a reduced set of inputs, and persisting those in the ODA for execution.

At the end of this script, you should be able to see the created SBDs
at {BASE_URL}/{PROJECT_ID}/{OBSERVING_BLOCK_ID}
"""

import requests
from temptokens import *

from ska_oso_services.odt.service.mid_example.sbd_generator import (
    generate_mid_commissioning_five_point_sbd,
)

BASE_URL = "https://k8s.stfc.skao.int/staging-oso-cloud/oso/api/v16"
OSO_SERVICES_URL = f"{BASE_URL}/oso/api/v16"

PROJECT_ID = "prj-19qrcpp9kwh5"
OBSERVING_BLOCK_ID = "ob-19qrcpp9kxhn"

# SBD generation from a set of useful inputs
# Depending on the use case, the generator might return multiple SBDs, or you could
# loop over inputs multiple times. There is flexibility to make the inputs and generator
# as complex as you want.
# See https://gitlab.com/ska-telescope/oso/ska-oso-services/-/tree/mid-commissioning/src/ska_oso_services/odt/service?ref_type=heads
# for more inspiration
TARGETS = ["PKS 0408-65", "PKS 1934-63"]  # e.g. this could come from an input file

# Note: if these SBDs are to be scheduled via the engine, you might want to set observing_constraints in the SBD
sbd = generate_mid_commissioning_five_point_sbd(TARGETS, sbd_name="Another Live Mid Demo example")


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
