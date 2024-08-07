import getpass
import json
import keyring
import urllib.request
from .output_handler import print_error, print_success

AUTH_LOGIN_API_URL="https://prospect-api.versyx.net/api/auth/login"
AUTH_REFRESH_API_URL="https://prospect-api.versyx.net/api/auth/refresh"
CREDENTIAL_SERVICE_NAME = "ProspectorDeviceProfilingService"

def get_token_from_credential_manager(token_type: str) -> str:
    """
    Retrieves a token from the system's credential manager.

    Args:
        token_type (str): The type of token to retrieve (e.g., "AccessToken" or "RefreshToken").

    Returns:
        str: The token retrieved from the credential manager, or None if an error occurs or the token is not found.

    Raises:
        Exception: If an error occurs while accessing the credential manager.
    """

    try:
        return keyring.get_password(f"{CREDENTIAL_SERVICE_NAME}/{token_type}", token_type)
    except Exception as e:
        print_error(f"Failed to get {token_type} from credential manager: {e}")
    return None


def set_token_in_credential_manager(token_type: str, token: str) -> None:
    """
    Stores a token in the system's credential manager.

    Args:
        token_type (str): The type of token to store (e.g., "AccessToken" or "RefreshToken").
        token (str): The token value to store.

    Returns:
        None

    Raises:
        Exception: If an error occurs while accessing the credential manager.
    """

    try:
        keyring.set_password(f"{CREDENTIAL_SERVICE_NAME}/{token_type}", token_type, token)
        print_success(f"{token_type} saved to credential manager.")
    except Exception as e:
        print_error(f"Failed to save {token_type} to credential manager: {e}")


def authenticate_user(username: str, password: str) -> str:
    """
    Authenticates the user and obtains an access token and a refresh token.

    Args:
        username (str): The username for authentication.
        password (str): The password for authentication.

    Returns:
        dict: The authentication response containing tokens.

    Raises:
        urllib.error.HTTPError: If an HTTP error occurs during authentication.
        Exception: If an unexpected error occurs during authentication.
    """

    try:
        login_data = json.dumps({
            'email': username,
            'password': password
        }).encode("utf-8")

        login_request = urllib.request.Request(AUTH_LOGIN_API_URL)
        login_request.add_header('Content-Type', 'application/json; charset=utf-8')
        login_request.add_header('Content-Length', len(login_data))

        with urllib.request.urlopen(login_request, login_data) as response:
            response_data = json.load(response)
            print_success(f"Successfully authenticated with prospector service at {AUTH_LOGIN_API_URL}")

            return response_data
    except urllib.error.HTTPError as e:
        print_error(f"Failed to get access token: {e}")
        raise
    except Exception as e:
        print_error(f"Unexpected error during authentication: {e}")
        raise


def refresh_access_token(refresh_token: str) -> dict:
    """
    Refreshes the access token using the refresh token.

    Args:
        refresh_token (str): The refresh token.

    Returns:
        dict: The authentication response containing new tokens.

    Raises:
        urllib.error.HTTPError: If an HTTP error occurs during token refresh.
        Exception: If an unexpected error occurs during token refresh.
    """
    try:
        refresh_data = json.dumps({
            'refresh_token': refresh_token
        }).encode("utf-8")

        refresh_request = urllib.request.Request(AUTH_REFRESH_API_URL)
        refresh_request.add_header('Content-Type', 'application/json; charset=utf-8')
        refresh_request.add_header('Content-Length', len(refresh_data))

        with urllib.request.urlopen(refresh_request, refresh_data) as response:
            response_data = json.load(response)
            print_success(f"Successfully refreshed access token with prospector service at {AUTH_REFRESH_API_URL}")

            return response_data
    except urllib.error.HTTPError as e:
        print_error(f"Failed to refresh access token: {e}")
        raise
    except Exception as e:
        print_error(f"Unexpected error during token refresh: {e}")
        raise


def get_access_token():
    """
    Retrieves the access token from the credential manager or prompts for user credentials to obtain a
    new token.

    Returns:
        str: The access token.

    Raises:
        Exception: If an unexpected error occurs during token retrieval or authentication.
    """

    access_token = get_token_from_credential_manager("AccessToken")
    if not access_token:
        username = input("Enter your username: ")
        password = getpass.getpass(prompt="Enter your password: ")

        auth_response = authenticate_user(username, password)
        set_token_in_credential_manager("AccessToken", auth_response['access_token'])
        set_token_in_credential_manager("RefreshToken", auth_response['refresh_token'])
        access_token = auth_response['access_token']
    
    return access_token

