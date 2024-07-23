import hashlib
import json
import msvcrt
import os
import platform
import re
import subprocess
import winreg


def snake(str: str) -> str:
    """
    Converts a CamelCase string to snake_case.

    Args:
        str (str): The string to convert.

    Returns:
        str: The converted string in snake_case.
    """
    return re.sub(r'(?<!^)(?=[A-Z])', '_', str).lower()


def open_key(hive, path) -> winreg.HKEYType:
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
    reg_key = open_key(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System")
    reg_key_b = open_key(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS")
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
                output[snake(memory[o])] = ''
            
            if d != 0 and d % 1 == 0:
                multi = multi + 1
                
            values = memory[offset*multi:]
            
            for v in range(offset):
                key = snake(memory[v])
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


def get_hwid() -> hashlib._hashlib.HASH:
    """
    Retrieves the hardware ID (HWID) and generates a SHA-256 hash.

    Returns:
        hashlib._hashlib.HASH: The SHA-256 hash of the HWID.
    """
    id = str(subprocess.check_output('wmic csproduct get uuid'), 'utf-8').split('\n')[1].strip()
    
    return hashlib.sha256(id.encode('utf-8'))


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
        'hwid': get_hwid().hexdigest(),
        'hostname': platform.node(),
        'os': {
            'platform': platform.system(),
            'distribution': get_distribution(),
            'arch': platform.architecture()[0],
            'kernel': platform.version(),
        },
        'software': {
            'programs': installed_software,
            'num_installed': len(installed_software)
        },
        'hardware': {
            'bios': get_bios(),
            'cpu': {
                'name': platform.processor(),
                'cores': os.cpu_count(),
            },
            'ram': get_memory()
        }    
    }

    return profile


def write_profile(profile: dict):
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

    with open(destination, 'w') as prospectorfile:
        prospectorfile.write(content)
        print('device profile written to ' + destination)


def main():
    """
    Main function to generate and write the system profile.
    """
    profile = get_profile()
    print(json.dumps(profile, sort_keys=False, indent=4))
    write_profile(profile)


if __name__ == '__main__':
    main()
    print("Press any key to exit...")
    msvcrt.getch()
