
import ctypes
import getpass
import hashlib
import os
import re
import socket
import subprocess
import winreg
from .registry_handler import open_reg_key
from .output_handler import print_error, to_snake_case


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

