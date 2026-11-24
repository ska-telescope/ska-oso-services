import os

TEST_BASE_API_URL = "/ska-oso-services/oso/api/v0"
ODT_BASE_API_URL = f"{TEST_BASE_API_URL}/odt"
PHT_BASE_API_URL = f"{TEST_BASE_API_URL}/pht"

# The tests read the OSD's tmdata at a commit published to the CAR, rather than
# the application's default of OSD main, so a change to the OSD's data can't
# break them. Update it to test against newer OSD data.
OSD_TMDATA = "car:ost/ska-ost-osd?~2fd1238d37eefe459757e2372df45cc4b2813111#tmdata"


def pytest_configure():
    # Set test defaults early so settings created during module imports use these values.
    os.environ.setdefault("API_PATH_PREFIX", TEST_BASE_API_URL)
    os.environ.setdefault("SKA_AUTH_AUDIENCE", "test:pht,test:odt")
    os.environ.setdefault(
        "SDP_SCRIPT_TMDATA",
        f"file://{os.path.join(os.path.dirname(__file__), 'tmdata')}",
    )
    os.environ.setdefault("OSD_TMDATA", OSD_TMDATA)
