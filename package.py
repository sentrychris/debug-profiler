import os
import shutil
import subprocess
import sys
import zipfile
import requests


UPX_VERSION = "4.2.4"
UPX_RELEASE = f"upx-{UPX_VERSION}-win64"
SPEC_FILE = "prospector.spec"
BUILD_DIR = "./build"
DIST_DIR = "./dist"
CWD = os.path.dirname(os.path.abspath(__file__))


def check_file_exists(filepath):
    if not os.path.exists(filepath):
        print(f"This script must be run from the same directory containing {SPEC_FILE}")
        sys.exit(1)


def prepare_upx():
    print("Downloading UPX...")
    url = f"https://github.com/upx/upx/releases/download/v{UPX_VERSION}/{UPX_RELEASE}.zip"
    zip_path = os.path.join(CWD, f"{UPX_RELEASE}.zip")
    response = requests.get(url)
    with open(zip_path, 'wb') as file:
        file.write(response.content)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(CWD)
    os.remove(zip_path)


def clean_directory(directory):
    if os.path.exists(directory):
        print(f"Cleaning {directory} directory...")
        shutil.rmtree(directory)


def main():
    os.chdir(CWD)

    check_file_exists(os.path.join(CWD, SPEC_FILE))

    print(f"Building {SPEC_FILE}...")

    print("Checking for UPX...")
    if not os.path.exists(os.path.join(CWD, UPX_RELEASE)):
        prepare_upx()
    else:
        print("UPX is available")

    clean_directory(BUILD_DIR)
    clean_directory(DIST_DIR)

    subprocess.run(["pyinstaller", SPEC_FILE, "--upx-dir", os.path.join(CWD, UPX_RELEASE)], check=True)

    print("Removing UPX")
    shutil.rmtree(os.path.join(CWD, UPX_RELEASE))


if __name__ == "__main__":
    main()
