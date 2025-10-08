"""
This module provides functions to retrieve SDP script versions and parameters
from TMData. It uses the ska_telmodel library to access TMData and fetch the
required information.
"""

import os
from typing import Any

from ska_telmodel.data import TMData

DEFAULT_SOURCE = "gitlab://gitlab.com/ska-telescope/sdp/ska-sdp-script#tmdata"


def get_tmdata() -> TMData:
    return TMData([os.getenv("SDP_SCRIPT_TMDATA", DEFAULT_SOURCE)])


def get_script_versions(name: str) -> list[str]:
    """
    Fetches the SDP scripts versions from the TMData.

    :param name: Name of the script.
    :return: A list of Script versions for the supplied script name.
    """
    try:
        scripts = get_tmdata()["ska-sdp/scripts/scripts.yaml"].get_dict()

        # Extract the name, and versions for the supplied script
        script_versions = [
            script["version"]
            for script in scripts.get("scripts", [])
            if "name" in script and "version" in script and script["name"] == name
        ]

        return script_versions
    except KeyError as error:
        raise KeyError(f"Missing expected key in script versions: {error}")
    except ValueError as error:
        if "Base path does not exist" in str(error):
            raise ValueError(f"TMData base path error: {error}")
        raise


def get_script_params(name: str, version: str) -> dict[str, Any]:
    """
    Fetches the SDP script parameters from the TMData.

    :param name: Name of the script.
    :param version: Version of the script.
    :return: The SDP script parameter settings as a JSON schema.
    """
    try:
        tmdata = get_tmdata()
        scripts = tmdata["ska-sdp/scripts/scripts.yaml"].get_dict()

        # Find the script matching name and version, and get its schema
        script = next(
            (
                s
                for s in scripts.get("scripts", [])
                if s.get("name") == name
                and s.get("version") == version
                and "schema" in s
            ),
            None,
        )
        if not script:
            raise ValueError(
                f"Script '{name}' with version '{version}' not found or missing schema."
            )

        return tmdata[f"ska-sdp/scripts/{script['schema']}"].get_dict()
    except KeyError as error:
        raise KeyError(f"Missing expected key in script parameters: {error}")
    except ValueError as error:
        if "Base path does not exist" in str(error):
            raise ValueError(f"TMData base path error: {error}")
        raise
