__all__ = ["OSO_SERVICES_TOKEN", "OST_SERVICES_TOKEN", "get_headers"]


def get_headers(access_token) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


OSO_SERVICES_TOKEN = "COPY TOKEN HERE"

OST_SERVICES_TOKEN = "COPY TOKEN HERE"
