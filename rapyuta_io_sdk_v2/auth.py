import httpx
from typing import Optional
from rapyuta_io_sdk_v2.exceptions import AuthenticationError

def authenticate(email: str, password: str,environment: str) -> Optional[str]:
    url = f"https://{environment}rip.apps.okd4v2.okd4beta.rapyuta.io/user/login"
    try:
        response = httpx.post(url,json={'email':email,'password':password})
        auth_token = response.json()
        if auth_token and auth_token["success"]:
            return auth_token["data"]["token"]
        raise AuthenticationError()
    except AuthenticationError as e:
        raise
    except Exception as e:
        raise

