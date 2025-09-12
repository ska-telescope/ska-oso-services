from os import getenv

import msal
import requests

AUDIENCE = getenv("SKA_AUTH_AUDIENCE", "api://e4d6bb9b-cdd0-46c4-b30a-d045091b501b")

TENANT_ID = "78887040-bad7-494b-8760-88dcacfb3805"
CLIENT_ID = "e4d6bb9b-cdd0-46c4-b30a-d045091b501b"
CLIENT_SECRET = getenv("OSO_CLIENT_SECRET", "OSO_CLIENT_SECRET")

MS_GRAPH_URL = "https://graph.microsoft.com/v1.0"


config = {
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "authority": f"https://login.microsoftonline.com/{TENANT_ID}",
    "scope": ["https://graph.microsoft.com/.default"],
}

client = msal.ConfidentialClientApplication(
    config["client_id"],
    authority=config["authority"],
    client_credential=config["client_secret"],
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
    token_result = client.acquire_token_silent(config["scope"], account=None)

    if token_result:
        print("Access token loaded from cache.")
    else:
        token_result = client.acquire_token_for_client(scopes=config["scope"])
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
