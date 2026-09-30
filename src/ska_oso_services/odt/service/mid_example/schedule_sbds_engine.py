"""
This script is an example of scheduling SBDs using the OST engine, to be executed by the OET.

It sends a list of SBDs and a window of time they should be scheduled in. The engine
will schedule as many of the SBDs as it can within that window, taking into account constraints within the SBD.

A use case for this might be that you have the telescope booked for tonight, and have a
bucket of commissioning SBDs you just need observing at some point.

At the end of this script, you should be able to see the scheduled SBDs
at {BASE_URL}/ost/ and then monitor their execution from there.
"""

from datetime import datetime, timedelta

import requests
from temptokens import *

BASE_URL = "https://k8s.stfc.skao.int/staging-oso-mid"
OST_SERVICES_URL = f"{BASE_URL}/ost/api/v2"


# First decide get the SBDs to schedule. There are a few options:
#  - Query an OSO API for an existing SBD ID based on some criteria you want to observe (e.g. an observing block in my commissioning project)
#  - Have a list of your favourite SBDs handy
#  - Use the SBDs you have just created from a script (e.g. if build_and_persist_sbds.py was prepended to this)

SBD_IDS = ["sbd-1aw889e42jjh"]

# Now send the SBD_IDS to the scheduling engine for a queue. This will decide when
# to execute each SBD based on source visibility, resources availability and SBD constraints.
DUMMY_START_TIME = datetime.now()
DUMMY_END_TIME = DUMMY_START_TIME + timedelta(hours=3)
schedule_input = {
    "created_by": "system",
    "sbd_filter": {"sbd_list": SBD_IDS},
    "schedule_settings": {"start_time": DUMMY_START_TIME, "end_time": DUMMY_END_TIME},
}

ost_result = requests.post(
    f"{OST_SERVICES_URL}/observing_queue/subarray/", headers=get_headers(OST_SERVICES_TOKEN)
)

## Response will include which SBDs have been scheduled, and on which subarrays
print(ost_result.status_code)
print(ost_result.json())
