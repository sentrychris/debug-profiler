
import winreg
from .output_handler import print_error

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

