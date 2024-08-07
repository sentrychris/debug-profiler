import logging
import re


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
