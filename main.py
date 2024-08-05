import ctypes
import getpass
import hashlib
import json
import msvcrt
import os
import platform
import re
import socket
import subprocess
import urllib.request
import winreg


PROFILE_API_URL='https://prospect-api.versyx.net/api/devices/profiles'


class Color:
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

    print(f"{Color.GREEN}[success]{Color.RESET} {Color.WHITE}{message}{Color.RESET}")


def print_error(message: str) -> None:
    """
    Prints an error message in the terminal with the "[error]" label.

    Args:
        message (str): The error message to print.
    """

    print(f"{Color.RED}[error]{Color.RESET} {Color.WHITE}{message}{Color.RESET}")


def print_info(message) -> None:
    """
    Prints an informational message in the terminal with the "[info]" label in sky blue and the message in white.

    Args:
        message (str): The informational message to print.
    """
    print(f"{Color.BLUE}[info]{Color.RESET} {Color.WHITE}{message}{Color.RESET}")


def to_snake_case(str: str) -> str:
    """
    Converts a CamelCase string to snake_case.

    Args:
        str (str): The string to convert.

    Returns:
        str: The converted string in snake_case.
    """

    return re.sub(r'(?<!^)(?=[A-Z])', '_', str).lower()


def open_reg_key(hive, path) -> winreg.HKEYType:
    """
    Opens a registry key.

    Args:
        hive: The registry hive (e.g., winreg.HKEY_LOCAL_MACHINE).
        path (str): The registry path.

    Returns:
        winreg.HKEYType: The opened registry key.
    """

    return winreg.OpenKey(
        winreg.ConnectRegistry(None, hive),
        path,
        0,
        winreg.KEY_READ | winreg.KEY_WOW64_64KEY
    )


def get_bios() -> dict:
    """
    Retrieves BIOS information from the Windows registry.

    Returns:
        dict: A dictionary containing BIOS model and firmware version.
    """

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


def get_software(hive, flag) -> list:
    """
    Retrieves a list of installed software from the Windows registry.

    Args:
        hive: The registry hive (e.g., winreg.HKEY_LOCAL_MACHINE).
        flag: The registry access flag.

    Returns:
        list: A list of dictionaries, each containing software details.
    """

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


def get_memory() -> list:
    """
    Retrieves memory (RAM) information using WMIC.

    Returns:
        list: A list of dictionaries, each containing memory chip details.
    """

    wmic = subprocess.check_output(
        'wmic memorychip get DeviceLocator, Capacity, ConfiguredClockSpeed, DataWidth, Manufacturer, PartNumber'
    )

    memory = str(wmic, 'utf-8').split()

    devices = []
    multi = 1
    offset = 6
    num_devices = round(len(memory[offset:]) / offset)
    try:
        for d in range(num_devices):
            output = {}
            for o in range(offset):
                output[to_snake_case(memory[o])] = ''
            
            if d != 0 and d % 1 == 0:
                multi = multi + 1
                
            values = memory[offset*multi:]
            
            for v in range(offset):
                key = to_snake_case(memory[v])
                if key in ['capacity', 'configured_clock_speed', 'data_width']:
                    value = int(values[v])
                    if key == 'capacity': value = round(int(values[v]) / (1024.0 ** 3))
                else:
                    value = values[v]
                output[key] = value

            devices.append(output)
    except:
        pass
    
    return devices


def get_distribution() -> str:
    """
    Retrieves the operating system distribution name.

    Returns:
        str: The OS distribution name.
    """

    os = subprocess.Popen('systeminfo', stdout=subprocess.PIPE).communicate()[0]
    try:
        os = str(os, "latin-1")
    except:
        pass

    return re.search("OS Name:\s*(.*)", os).group(1).strip()


def get_hwid() -> str:
    """
    Retrieves the hardware ID (HWID) and generates a SHA-256 hash.

    Returns:
        str: The SHA-256 hash of the HWID.
    """

    id = str(subprocess.check_output('wmic csproduct get uuid'), 'utf-8').split('\n')[1].strip()
    
    return hashlib.sha256(id.encode('utf-8')).hexdigest()


def get_uptime() -> str:
    """
    Retrieves system uptime.

    This function reads the system uptime from the '/proc/uptime' file and formats
    it into a human-readable string.

    Returns:
        str: A string representing the system uptime in days, hours, minutes, and seconds.
            If the file cannot be read, returns an error message.
    """

    try:
        uptime_ms = ctypes.windll.kernel32.GetTickCount64()
        total_seconds = uptime_ms / 1000.0
    except Exception:
        return "N/A"

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


def get_user() -> str:
    """
    Retrieves the full username in the format 'DOMAIN\\username' or 'MACHINE\\username'.

    Returns:
        str: The full username in the format 'DOMAIN\\username' or 'MACHINE\\username'.
    """

    username = getpass.getuser()
    hostname = socket.gethostname()

    domain = os.getenv('USERDOMAIN')
    if domain is None:
        domain = hostname
    
    return f"{domain}\\{username}"


def get_profile() -> dict:
    """
    Gathers system profile information, including hardware, software, and OS details.

    Returns:
        dict: A dictionary containing the system profile.
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
            'ram': get_memory()
        },
        'software': {
            'programs': installed_software,
            'num_installed': len(installed_software)
        }   
    }

    return profile


def write_profile(profile: dict) -> None:
    """
    Writes the system profile to a JSON file in the user's home directory.

    Args:
        profile (dict): The system profile to write.
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
            print_success(f"Device profile written to {destination}")
    except Exception as e:
        print_error(f"Unable to write device profile: {e}")


def send_profile(profile: dict) -> None:
    """
    Sends the system profile to the prosect profiling service API.

    Args:
        profile (dict): The system profile to send.
    """

    try:
        content = json.dumps(profile, sort_keys=False, indent=4)
        request = urllib.request.Request(PROFILE_API_URL)
        request.add_header('Content-Type', 'application/json; charset=utf-8')
        request.add_header('Authorization', 'Bearer c2VjcmV0')
        data = content.encode('utf-8')
        request.add_header('Content-Length', len(data))

        urllib.request.urlopen(request, data)

        print_success(f"Device profile submitted to prospect service at {PROFILE_API_URL}")
    except Exception as e:
        print_error(f"Could not send profiling data to prospect service: {e}")


def main() -> None:
    """
    Main function to generate and write the system profile.
    """

    print_info("Collecting device profile...")
    print(" ")

    profile = get_profile()
    write_profile(profile)
    send_profile(profile)
    
    print(" ")


if __name__ == '__main__':
    main()
    print_info("Press any key to exit...")
    msvcrt.getch()
