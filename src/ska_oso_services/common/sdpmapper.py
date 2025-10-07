"""
This module provides functions to retrieve SDP script versions and parameters
from TMData. It uses the ska_telmodel library to access TMData and fetch the
required information.
"""

import os

from fastapi import HTTPException
from ska_telmodel.data import TMData

from ska_oso_services.common.error_handling import OSDError

default_source = "gitlab://gitlab.com/ska-telescope/sdp/ska-sdp-script#tmdata"


def get_script_versions(name: str) -> list[str]:
    """
    Fetches the SDP scripts versions from the TMData.

    :param name: Name of the script.
    :return: A list of Script versions for the supplied script name.
    """
    try:
        scripts_url = os.getenv("SDP_SCRIPT_TMDATA", default_source)
        tmdata = TMData([scripts_url])
        scripts = tmdata["ska-sdp/scripts/scripts.yaml"].get_dict()

        # Extract the name, and versions for the supplied script
        script_versions = [
            script["version"]
            for script in scripts.get("scripts", [])
            if "name" in script and "version" in script and script["name"] == name
        ]

        return script_versions
    except KeyError as error:
        raise OSDError(f"Missing expected key in script versions: {error}")
    except ValueError as error:
        if "Base path does not exist" in str(error):
            raise OSDError(f"TMData base path error: {error}")
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch SDP script versions: {error}"
        )


def get_script_params(name: str, version: str) -> dict:
    """
    Fetches the SDP script parameters from the TMData.

    :param name: Name of the script.
    :param version: Version of the script.
    :return: The SDP script parameter settings.
    """
    try:
        scripts_url = os.getenv("SDP_SCRIPT_TMDATA", default_source)
        tmdata = TMData([scripts_url])
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
            raise OSDError(
                f"Script '{name}' with version '{version}' not found or missing schema."
            )

        return tmdata[f"ska-sdp/scripts/{script["schema"]}"].get_dict()
    except KeyError as error:
        raise OSDError(f"Missing expected key in script parameters: {error}")
    except ValueError as error:
        if "Base path does not exist" in str(error):
            raise OSDError(f"TMData base path error: {error}")
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch SDP script parameters: {error}"
        )
