import argparse
import ctypes
import getpass
import hashlib
import keyring
import logging
import json
import msvcrt
import os
import platform
import re
import socket
import subprocess
import urllib.request
import winreg


AUTH_LOGIN_API_URL="https://prospect-api.versyx.net/api/auth/login"
AUTH_REFRESH_API_URL="https://prospect-api.versyx.net/api/auth/refresh"
PROFILE_API_URL="https://prospect-api.versyx.net/api/devices/profiles"
SERVICE_NAME = "ProspectorService"


logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


class Terminal:
    GREEN = '\033[92m'
    RED = '\033[91m'
    WHITE = '\033[97m'
    BLUE = '\033[96m'
    RESET = '\033[0m'


def print_success(message: str) -> None:
    """
    Prints a success message in the terminal with the "[success]" label.

    Args:
        message (str): The success message to print.
    """

    logging.info(f"{Terminal.GREEN}[success]{Terminal.RESET} {Terminal.WHITE}{message}{Terminal.RESET}")


def print_error(message: str) -> None:
    """
    Prints an error message in the terminal with the "[error]" label.

    Args:
        message (str): The error message to print.
    """

    logging.error(f"{Terminal.RED}[error]{Terminal.RESET} {Terminal.WHITE}{message}{Terminal.RESET}")


def print_info(message) -> None:
    """
    Prints an informational message in the terminal with the "[info]" label in sky blue and the message in white.

    Args:
        message (str): The informational message to print.
    """
    logging.info(f"{Terminal.BLUE}[info]{Terminal.RESET} {Terminal.WHITE}{message}{Terminal.RESET}")


def to_snake_case(str: str) -> str:
    """
    Converts a CamelCase string to snake_case.

    Args:
        str (str): The string to convert.

    Returns:
        str: The converted string in snake_case.
    """

    return re.sub(r'(?<!^)(?=[A-Z])', '_', str).lower()


def open_reg_key(hive, path, create=False) -> winreg.HKEYType:
    """
    Opens a registry key.

    Args:
        hive: The registry hive (e.g., winreg.HKEY_LOCAL_MACHINE).
        path (str): The registry path.
        create (bool): Whether or not we are creating keys

    Returns:
        winreg.HKEYType: The opened registry key.
    """

    try:
        permissions = winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        if create:
            permissions |= winreg.KEY_WRITE | winreg.KEY_CREATE_SUB_KEY

        return winreg.OpenKey(
            winreg.ConnectRegistry(None, hive),
            path,
            0,
            permissions
        )
    except FileNotFoundError:
        if create:
            return winreg.CreateKey(hive, path)
        else:
            print_error(f"Registry path not found: {path}")
            return None
    except PermissionError:
        print_error(f"Permission denied: {path}")
        return None
    except Exception as e:
        print_error(f"Failed to open registry key: {e}")
        return None


def get_bios() -> dict:
    """
    Retrieves BIOS information from the Windows registry.

    Returns:
        dict: A dictionary containing BIOS model and firmware version.
    """

    try:
        reg_key = open_reg_key(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System")
        reg_key_b = open_reg_key(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS")
        version = winreg.QueryValueEx(reg_key, "SystemBiosVersion")
        model = [
            winreg.QueryValueEx(reg_key_b, "BaseBoardManufacturer")[0],
            winreg.QueryValueEx(reg_key_b, "BaseBoardProduct")[0]
        ]

        return {
            'model': ' '.join(model),
            'firmware': ' '.join(version[0]),
        }
    except Exception as e:
        print_error(f"Failed to get BIOS information: {e}")
        return {}


def get_software(hive, flag) -> list:
    """
    Retrieves a list of installed software from the Windows registry.

    Args:
        hive: The registry hive (e.g., winreg.HKEY_LOCAL_MACHINE).
        flag: The registry access flag.

    Returns:
        list: A list of dictionaries, each containing software details.
    """

    try:
        reg_key = winreg.OpenKey(
            winreg.ConnectRegistry(None, hive),
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            0,
            winreg.KEY_READ | flag
        )
        count_subkey = winreg.QueryInfoKey(reg_key)[0]
        software_list = []
        for i in range(count_subkey):
            software = {}
            try:
                sub_key = winreg.OpenKey(reg_key, winreg.EnumKey(reg_key, i))
                software['name'] = winreg.QueryValueEx(sub_key, "DisplayName")[0]
                try:
                    software['version'] = winreg.QueryValueEx(sub_key, "DisplayVersion")[0]
                except EnvironmentError:
                    software['version'] = 'undefined'
                try:
                    software['publisher'] = winreg.QueryValueEx(sub_key, "Publisher")[0]
                except EnvironmentError:
                    software['publisher'] = 'undefined'
                software_list.append(software)
            except EnvironmentError:
                continue

        return software_list
    except Exception as e:
        print_error(f"Failed to get software information: {e}")
        return []


def get_memory() -> list:
    """
    Retrieves memory (RAM) information using WMIC.

    Returns:
        list: A list of dictionaries, each containing memory chip details.
    """

    try:
        wmic = subprocess.check_output(
            'wmic memorychip get DeviceLocator, Capacity, ConfiguredClockSpeed, DataWidth, Manufacturer, PartNumber'
        )

        memory = str(wmic, 'utf-8').split()

        devices = []
        multi = 1
        offset = 6
        num_devices = round(len(memory[offset:]) / offset)
        for d in range(num_devices):
            output = {}
            for o in range(offset):
                output[to_snake_case(memory[o])] = ''

            if d != 0 and d % 1 == 0:
                multi = multi + 1
            values = memory[offset * multi:]
            for v in range(offset):
                key = to_snake_case(memory[v])
                if key in ['capacity', 'configured_clock_speed', 'data_width']:
                    value = int(values[v])
                    if key == 'capacity': value = round(int(values[v]) / (1024.0 ** 3))
                else:
                    value = values[v]
                output[key] = value

            devices.append(output)

        return devices
    except Exception as e:
        print_error(f"Failed to collect memory data: {e}")
        return []


def get_disks() -> list:
    """
    Retrieves disk information using WMIC.

    Returns:
        list: A list of dictionaries, each containing disk details.
    """

    try:
        wmic = subprocess.check_output(
            'wmic diskdrive get Model, Size, MediaType, SerialNumber, Status', shell=True
        )
        disk_info = str(wmic, 'utf-8').strip().split('\n')
        disks = []
        
        for disk in disk_info[1:]:
            parts = [p.strip() for p in disk.split() if p]
            
            if len(parts) >= 5:
                model = ' '.join(parts[:-4])
                size = parts[-2]
                try:
                    size = int(size) // (1024**3)
                except ValueError:
                    size = parts[-2]
                
                disks.append({
                    'model': model,
                    'size_gb': size,
                    'media_type': parts[-5],
                    'serial_number': parts[-4],
                    'status': parts[-1]
                })
        
        return disks
    except Exception as e:
        print_error(f"Failed to get disk information: {e}")
        return []


def get_gpus() -> list:
    """
    Retrieves GPU information using WMIC.

    Returns:
        list: A list of dictionaries, each containing GPU details.
    """

    try:
        wmic = subprocess.check_output('wmic path win32_VideoController get Name, DriverVersion, Status', shell=True)
        gpu_info = str(wmic, 'utf-8').strip().split('\n')[1:]
        gpus = []
        for gpu in gpu_info:
            parts = [p.strip() for p in gpu.split('  ') if p]
            if len(parts) == 3:
                gpus.append({
                    'name': parts[1],
                    'driver_version': parts[0],
                    'status': parts[2]
                })

        return gpus
    except Exception as e:
        print_error(f"Failed to get GPU information: {e}")
        return []


def get_network_interfaces() -> list:
    """
    Retrieves network interface information using WMIC.

    Returns:
        list: A list of dictionaries, each containing network interface details.
    """

    try:
        wmic = subprocess.check_output('wmic nic get Name, MACAddress, Speed, Manufacturer, Description', shell=True)
        lines = str(wmic, 'utf-8').strip().split('\n')
        
        headers = re.split(r'\s{2,}', lines[0].strip())
        headers = [header.strip().lower().replace(' ', '_') for header in headers]
        
        network_info = lines[1:]
        interfaces = []

        for line in network_info:
            parts = re.split(r'\s{2,}', line.strip())
            interface = {}
            
            if len(parts) == 3:
                # Case where there are three values: description, manufacturer, name
                interface['description'] = parts[0]
                interface['manufacturer'] = parts[1]
                interface['name'] = parts[2]
            else:
                # Case where there are five values
                for idx, header in enumerate(headers):
                    if idx < len(parts):
                        interface[header] = parts[idx]
                    else:
                        interface[header] = ''
            
            interfaces.append(interface)
        
        return interfaces
    except Exception as e:
        print_error(f"Failed to get network information: {e}")
        return []


def get_connected_wifi() -> dict:
    """
    Retrieves information about the currently connected Wi-Fi network using netsh.

    Returns:
        dict: A dictionary containing Wi-Fi connection details, including the password.
    """

    try:
        wifi_info = subprocess.check_output('netsh wlan show interfaces', shell=True)
        wifi_info = str(wifi_info, 'utf-8').strip().split('\n')

        include_keys = [
            'authentication',
            'band',
            'bssid',
            'channel',
            'description',
            'guid',
            'physical_address',
            'radio_type',
            'ssid',
            'state',
            'receive_rate_(mbps)',
            'transmit_rate_(mbps)'
        ]
        
        wifi_details = {}
        ssid = None
        for line in wifi_info:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                if key in include_keys:
                    wifi_details[key] = value
                if key == 'ssid':
                    ssid = value
        
        if ssid:
            profile_info = subprocess.check_output(f'netsh wlan show profile name="{ssid}" key=clear', shell=True)
            profile_info = str(profile_info, 'utf-8').strip().split('\n')
            for line in profile_info:
                if 'Key Content' in line:
                    key, value = line.split(':', 1)
                    wifi_details['password'] = value.strip()
                    break
        
        return wifi_details
    except Exception as e:
        print_error(f"Failed to get connected Wi-Fi information: {e}")
        return {}


def get_distribution() -> str:
    """
    Retrieves the operating system distribution name.

    Returns:
        str: The OS distribution name.
    """

    try:
        os = subprocess.Popen('systeminfo', stdout=subprocess.PIPE).communicate()[0]
        distro = str(os, "latin-1")

        return re.search("OS Name:\s*(.*)", distro).group(1).strip()
    except Exception as e:
        print_error(f"Failed to get distribution information: {e}")
        return "N/A"


def get_uptime() -> str:
    """
    Retrieves system uptime.

    Returns:
        str: A string representing the system uptime in days, hours, minutes, and seconds.
            If the file cannot be read, returns an error message.
    """

    try:
        uptime_ms = ctypes.windll.kernel32.GetTickCount64()
        total_seconds = uptime_ms / 1000.0
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        uptime_parts = [
            f"{int(days)} day{'s' if days != 1 else ''}" if days else "",
            f"{int(hours)} hr{'s' if hours != 1 else ''}" if hours else "",
            f"{int(minutes)} min{'s' if minutes != 1 else ''}" if minutes else "",
            f"{int(seconds)} sec{'s' if seconds != 1 else ''}" if seconds else ""
        ]

        return ", ".join(part for part in uptime_parts if part)
    except Exception as e:
        print_error(f"Failed to get system uptime: {e}")
        return "N/A"


def get_user() -> str:
    """
    Retrieves the full username in the format 'DOMAIN\\username' or 'MACHINE\\username'.

    Returns:
        str: The full username in the format 'DOMAIN\\username' or 'MACHINE\\username'.
    """

    try:
        username = getpass.getuser()
        hostname = socket.gethostname()

        domain = os.getenv('USERDOMAIN')
        if domain is None:
            domain = hostname

        return f"{domain}\\{username}"
    except Exception as e:
        print_error(f"Failed to get user information: {e}")
        return "N/A"


def get_hwid() -> str:
    """
    Retrieves the hardware ID (HWID) and generates a SHA-256 hash.

    Returns:
        str: The SHA-256 hash of the HWID.
    """

    try:
        id = str(subprocess.check_output('wmic csproduct get uuid'), 'utf-8').split('\n')[1].strip()
        return hashlib.sha256(id.encode('utf-8')).hexdigest()
    except Exception as e:
        print_error(f"Failed to get HWID: {e}")
        return "N/A"


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
        return keyring.get_password(SERVICE_NAME, token_type)
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
        keyring.set_password(SERVICE_NAME, token_type, token)
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


def new_profile(send_to_service: bool) -> dict:
    """
    Main function to generate and write the device profile.
    """

    print_info("Collecting device profile...")

    try:
        profile = get_profile()

        write_profile(profile)

        if send_to_service:
            access_token = get_access_token()
            send_profile(access_token, profile)

        return profile
    except Exception as e:
        print_error(f"Failed to collect device profile: {e}")
        return {}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Collect and send prospector device profiles for Windows.")
    parser.add_argument('--silent', action="store_true", help="Run without user input (note: user must authenticate first).")
    parser.add_argument('--send', action="store_true", help="Send device profile to the prospector service.")
    args = parser.parse_args()

    profile = new_profile(args.send)
    if profile and not args.silent:
        print_info("Press 'p' to print device profile or any other key to exit...")
        key = msvcrt.getch()
        if key.lower() == b'p':
            print(json.dumps(profile, indent=4))

    print_info("Exiting...")
