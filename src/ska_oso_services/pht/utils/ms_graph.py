import msal
import requests

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
)


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
            except Exception as e:
                raise RuntimeError(f"Error fetching data from Graph API: {e}") from e
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
    url = f"{MS_GRAPH_URL}/users?$filter=mail eq '{email}'"
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

    return [
        member
        for member in members
        if member.get("@odata.type") == "#microsoft.graph.user"
    ]
