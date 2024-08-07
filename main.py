import argparse
import logging
import json
import msvcrt
from app.auth_handler import get_access_token
from app.profile_handler import get_profile, write_profile, send_profile
from app.output_handler import print_info, print_error


PROFILE_API_URL="https://prospect-api.versyx.net/api/devices/profiles"


logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def run_prospector(send_to_service: bool) -> dict:
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

    profile = run_prospector(args.send)
    if profile and not args.silent:
        print_info("Press 'p' to print device profile or any other key to exit...")
        key = msvcrt.getch()
        if key.lower() == b'p':
            print(json.dumps(profile, indent=4))

    print_info("Exiting...")
