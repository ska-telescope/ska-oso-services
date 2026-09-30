"""
This script is an example of scheduling SBDs manually via the OST, to be executed by the OET.

Manual means the scheduling engine/algorithm is not being used, and the SBD is being
set to execute at the start time that is set in this script. The only validation the
OST will do is to check something else isn't scheduled within the same window.

It could be prepended with a script like build_and_persist_sbds.py to build and schedule
SBDs on the fly, or it could be used to schedule existing, re-useable SBDs.

At the end of this script, you should be able to see the scheduled SBDs
at {BASE_URL}/ost/ and then monitor their execution from there.
"""

import datetime

import requests
from temptokens import *

BASE_URL = "https://k8s.stfc.skao.int/staging-oso-mid"
OSO_SERVICES_URL = f"{BASE_URL}/ost/api/v2"


# First decide get the SBDs to schedule. There are a few options:
#  - Query an OSO API for an existing SBD ID based on some criteria you want to observe
#  - Have a list of your favourite SBDs handy that you know the time you want to observe at
#  - Use the SBDs you have just created from a script (e.g. if build_and_persist_sbds.py was prepended to this)

SBD_IDS = ["sbd-1aw889e42jjh"]


# Now add the SBD_IDS to the queue at a specific time.
# This is used to execute SBDs at specific start times. Alternatively could just let the scheduler decide when
# to execute based on SBD (i.e. based on source visibility, resources availability and SBD constraints)

DUMMY_START_TIME = datetime.datetime.now()
DUMMY_DURATION_MIN = datetime.timedelta(minutes=1)  # should be able to get this from the SBD

QUEUE_ID = "obsq-10r3antb2dkz"  # need to query this from the OST
for sbd_id in SBD_IDS:
    queue_item = {
        "items": [
            {
                "sbd_fk": sbd_id,
                "queue_fk": QUEUE_ID,
                "is_executed": False,
                "sbd_version": 1,
                "subarray_id": 1,
                "observation_start_time": DUMMY_START_TIME.isoformat(),
                "observation_end_time": (DUMMY_START_TIME + DUMMY_DURATION_MIN).isoformat(),
                "sbd_duration_min": DUMMY_DURATION_MIN.seconds / 60,
                "window_period_min": 1,
            }
        ],
        "is_active": True,
        "create_env": True,
    }

    ost_result = requests.post(
        "https://k8s.stfc.skao.int/dev-ska-oso-ost-services-thad-test/ost/api/v2/observing_queue/subarray/",
        headers=get_headers(OST_SERVICES_TOKEN),
    )

    print(ost_result.status_code)
    print(ost_result.json())
