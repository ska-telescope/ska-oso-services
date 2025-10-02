"""
This module provides functions to retrieve SDP script versions and parameters
from TMData. It uses the ska_telmodel library to access TMData and fetch the
required information.
"""

import os

from ska_telmodel.data import TMData

from ska_oso_services.common.error_handling import OSDError

local_source = "file://tmdata"


def get_scriptVersions() -> dict:
    """
    Fetches the SDP scripts versions from the TMData.

    :return: An instance of ScriptVersions containing the SDP scripts version details.
    """
    try:
        scripts_url = os.getenv("SDP_SCRIPT_TMDATA", local_source)
        tmdata = TMData([scripts_url])
        scripts = tmdata["ska-sdp/scripts/scripts.yaml"].get_dict()

        # Extract the name, version, and assosiated param schema for each script
        script_versions = [
            {
                "name": script["name"],
                "version": script["version"],
                "params": script["schema"],
            }
            for script in scripts.get("scripts", [])
            if "name" in script and "version" in script and "schema" in script
        ]

        return script_versions
    except Exception as error:
        raise OSDError(f"Failed to fetch SDP script versions: {error}")


def get_scriptParams(name: str, version: str) -> dict:
    """
    Fetches the SDP script parameters from the TMData.

    :param name: Name of the script.
    :param version: Version of the script.
    :return: The SDP script parameter default settings.
    """
    try:
        scripts_url = os.getenv("SDP_SCRIPT_TMDATA", local_source)
        tmdata = TMData([scripts_url])
        params = tmdata[
            f"ska-sdp/scripts/{name}/{name}-params-{version}.json"
        ].get_dict()
        properties = params.get("properties", {})
        defaults = {
            key: value.get("default")
            for key, value in properties.items()
            if "default" in value
        }

        return defaults
    except Exception as error:
        raise OSDError(f"Failed to fetch SDP script parameters: {error}")
