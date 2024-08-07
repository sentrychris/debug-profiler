import json
import os
import platform
import urllib.request
import winreg
from .system_metrics import get_hwid, get_disks, get_memory, get_gpus, \
    get_bios, get_distribution, get_uptime, get_user, get_software, \
    get_network_interfaces,  get_connected_wifi
from .auth_handler import get_token_from_credential_manager, set_token_in_credential_manager, \
    refresh_access_token
from .output_handler import print_error, print_info, print_success


PROFILE_API_URL="https://prospect-api.versyx.net/api/devices/profiles"


def get_profile() -> dict:
    """
    Gathers device profile information, including hardware, software, and OS details.

    Returns:
        dict: A dictionary containing the device profile.
    """

    installed_software = get_software(
        winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY
    ) + get_software(
        winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY
    ) + get_software(
        winreg.HKEY_CURRENT_USER, 0
    )

    profile = {
        'hwid': get_hwid(),
        'hostname': platform.node(),
        'user': get_user(),
        'uptime': get_uptime(),
        'os': {
            'platform': platform.system(),
            'distribution': get_distribution(),
            'arch': platform.architecture()[0],
            'version': platform.version(),
        },
        'hardware': {
            'bios': get_bios(),
            'cpu': {
                'name': platform.processor(),
                'cores': os.cpu_count(),
            },
            'ram': get_memory(),
            'disks': get_disks(),
            'gpus': get_gpus()
        },
        'network': {
            'wifi': get_connected_wifi(),
            'interfaces': get_network_interfaces()
        },
        'software': {
            'programs': installed_software,
            'num_installed': len(installed_software)
        },
        'source_api': PROFILE_API_URL
    }

    return profile


def write_profile(profile: dict) -> None:
    """
    Writes the device profile to a JSON file in the user's home directory.

    Args:
        profile (dict): The device profile to write.
    """

    filename = 'prospector-profile-' + profile.get('hwid')[:8] + '.json'
    filepath = os.path.join(os.path.expanduser('~'), '.prospector')

    if not os.path.isdir(filepath):
        os.mkdir(filepath)

    content = json.dumps(profile, sort_keys=False, indent=4)
    destination = os.path.join(filepath, filename)

    try:
        with open(destination, 'w') as prospectorfile:
            prospectorfile.write(content)
            print_success(f"Wrote new device profile to {destination}")
    except Exception as e:
        print_error(f"Failed to write new device profile: {e}")


def send_profile(access_token: str, profile: dict) -> None:
    """
    Sends the device profile to the prosector service.

    Args:
        profile (dict): The device profile to send.
    """

    try:
        profile_data = json.dumps(profile, sort_keys=False, indent=4).encode('utf-8')

        profile_request = urllib.request.Request(PROFILE_API_URL)
        profile_request.add_header('Content-Type', 'application/json; charset=utf-8')
        profile_request.add_header('Authorization', f'Bearer {access_token}')
        profile_request.add_header('Content-Length', len(profile_data))

        urllib.request.urlopen(profile_request, profile_data)

        print_success(f"Submitted device profile to prospector service at {PROFILE_API_URL}")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print_info(f"Access token expired. Refreshing token...")

            refresh_token = get_token_from_credential_manager("RefreshToken")
            if not refresh_token:
                print_error("Refresh token not found. Please authenticate again.")
                raise

            auth_response = refresh_access_token(refresh_token)
            set_token_in_credential_manager("AccessToken", auth_response['access_token'])
            set_token_in_credential_manager("RefreshToken", auth_response['refresh_token'])

            # Retry sending the profile with the new access token
            send_profile(auth_response['access_token'], profile)
        else:
            print_error(f"Failed to send device profile to profile service: {e}")
            raise
    except Exception as e:
        print_error(f"Unexpected error during profile submission: {e}")
        raise

