import re
from typing import Optional
from urllib.parse import quote

import jwt
import msal
import requests
from ska_oso_pdm.proposal import Proposal

from ska_oso_services.pht.utils.constants import (
    CLIENT_ID,
    CLIENT_SECRET,
    MS_GRAPH_URL,
    SCOPE,
    TENANT_ID,
)

client = msal.ConfidentialClientApplication(
    client_id=CLIENT_ID,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    client_credential=CLIENT_SECRET,
    token_cache=None,
)

_GRAPH_SELECT_OFFICE = "officeLocation"


def extract_profile_from_access_token(auth) -> tuple[str, str, str]:
    """
    Returns (given_name, family_name, email) from an already-verified access token.
    """
    # TODO: remove this entire function when the final decision
    # about how to save the investigators details is made

    token = getattr(auth, "access_token", "") or ""
    if token.startswith("Bearer "):
        token = token.split(" ", 1)[1]

    try:
        claims = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
    except jwt.InvalidTokenError:
        return "", "", ""

    given = claims.get("given_name") or ""
    family = claims.get("family_name") or ""

    email = claims.get("upn")

    return given, family, email


def make_graph_call(url, pagination=True):
    """
    Make an authenticated call to the Microsoft Graph API.

    This function acquires an access token from Microsoft Entra using MSAL
    and sends a GET request to the specified Graph API URL and supports optional
    pagination if the API response contains an '@odata.nextLink'.

    Args:
        url (str): The full Microsoft Graph API URL to request.
        pagination (bool, optional): If True, will follow '@odata.nextLink' to fetch
            additional pages of results. Defaults to True.

    Returns:
        list: Returns a list of objects if the response contains a "value" key
        (collection endpoint).
        Returns an empty list if the request fails or no token is acquired.
    """

    token_result = client.acquire_token_silent(SCOPE, account=None)

    if token_result:
        print("Access token loaded from cache.")
    else:
        token_result = client.acquire_token_for_client(scopes=SCOPE)
        print("New access token acquired from MS Entra")

    if "access_token" in token_result:
        headers = {"Authorization": "Bearer " + token_result["access_token"]}
        graph_results = []

        while url:
            try:
                graph_result = requests.get(url, headers=headers).json()
                graph_results.extend(graph_result.get("value", []))
                if pagination and "@odata.nextLink" in graph_result:
                    url = graph_result["@odata.nextLink"]
                else:
                    url = None
            except Exception as err:
                raise RuntimeError(f"Error fetching data from Graph API: {err}") from err
        return graph_results
    else:
        error = token_result.get("error")
        description = token_result.get("error_description")
        raise RuntimeError(f"Failed to acquire token: {error} - {description}")


def get_users_by_mail(email: str):
    """
    Retrieve a list of users from Microsoft Graph by email address.

    Args:
        email (str): The email address of the user to search for.

    Returns:
        list: A list of user objects matching the email.
        Returns an empty list if no users
        are found or if the API call fails.
    """
    if not re.match(r"^[A-Za-z0-9._+-]+@[A-Za-z0-9._-]+\.[a-zA-Z]{2,}$", email):
        return []

    escaped = email.replace("'", "''")
    ms_graph_filter = f"mail eq '{escaped}' or userPrincipalName eq '{escaped}'"
    url = f"{MS_GRAPH_URL}/users?$filter={quote(ms_graph_filter, safe='')}"
    return make_graph_call(url, pagination=False)


def get_users_by_group_id(group_id):
    """
    Retrieve a list of users from Microsoft Graph by group id.

    Args:
        group_id (str): The group id of the user to search for.

    Returns:
        list: A list of user objects matching the group id.
        Returns an empty list if no users
        are found or if the API call fails.
    """
    members_url = f"{MS_GRAPH_URL}/groups/{group_id}/members"
    members = make_graph_call(members_url, False)

    return [member for member in members if member.get("@odata.type") == "#microsoft.graph.user"]


def _extract_pi_user_id(proposal: Proposal) -> Optional[str]:
    """
    Return the user_id (string) of the principal investigator on the proposal.
    """
    proposal_info = getattr(proposal, "proposal_info", None)
    if proposal_info is None:
        return None

    investigators = getattr(proposal_info, "investigators", None) or []
    if not investigators:
        return None

    for inv in investigators:
        if not getattr(inv, "principal_investigator", False):
            continue

        user_id = getattr(inv, "user_id", None)
        if not user_id:
            return None

        user_id_str = str(user_id).strip()
        return user_id_str or None

    return None


def get_pi_office_location(proposal: Proposal) -> Optional[str]:
    """
    Fetch the location for the PI.
    """

    uid = _extract_pi_user_id(proposal)
    if not uid:
        return None

    url = f"{MS_GRAPH_URL}/users/{quote(uid, safe='')}?$select={_GRAPH_SELECT_OFFICE}"
    user = make_graph_call(url, pagination=False)

    if isinstance(user, dict):
        return user.get(_GRAPH_SELECT_OFFICE)

    return None
