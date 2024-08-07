import os
import shutil
import subprocess
import sys
import zipfile
import urllib.request


BUILD_SPEC = "prospector.spec"
UPX_VERSION = "4.2.4"


def print_usage():
    """
    Prints the usage information for the script and exits.

    This function provides instructions on how to use the script, including
    the available build types and an example of how to run the script.
    """

    print("Usage: Build Windows binary executable for prospector device profiling.\n")
    print("Example:")
    print("  python build.py\n")
    sys.exit(1)


def prepare_upx(pkg_dir: str, upx_ver: str) -> str:
    """
    Checks for the presence of UPX, downloads and extracts it if not present.

    Args:
        pkg_dir (str): The directory where the UPX package should be located.
        upx_ver (str): The version of UPX to check/download.
        upx_url (str): The URL from which to download the UPX package.

    Returns:
        upx_dir (str): The directory where the UPX package is located.
    """

    upx_file = f"upx-{upx_ver}-win64.zip"
    upx_path = os.path.join(pkg_dir, upx_file)
    upx_url = f"https://github.com/upx/upx/releases/download/v{upx_ver}/{upx_file}"
    
    if not os.path.exists(upx_path):
        print("Downloading UPX...")
        urllib.request.urlretrieve(upx_url, upx_path)

        with zipfile.ZipFile(upx_path, 'r') as zip_ref:
            zip_ref.extractall(pkg_dir)
                
        os.remove(upx_path)
    else:
        print("UPX is available")

    return upx_path[:-4]


def clean_directory(directory: str):
    """
    Deletes the specified directory and all its contents if it exists.

    Args:
        directory (str): The directory to be cleaned.
    """

    if os.path.exists(directory):
        print(f"Cleaning {directory} directory...")
        shutil.rmtree(directory)


def main():
    pwd = os.getcwd()
    build_dir = os.path.join(pwd, "build")
    dist_dir = os.path.join(pwd, "dist")
    pkg_dir = os.path.join(pwd, "package")
    spec_file = os.path.join(pkg_dir, BUILD_SPEC)

    print("Performing prebuild cleanup...")
    clean_directory(build_dir)
    clean_directory(dist_dir)

    print("Preparing UPX...")
    upx_dir = prepare_upx(pkg_dir, UPX_VERSION)

    print("Building prospector binary executable...")
    subprocess.run(["pyinstaller", spec_file, "--upx-dir", upx_dir], check=True)

    print("Removing UPX...")
    clean_directory(upx_dir)


if __name__ == "__main__":
    main()
