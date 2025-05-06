"""
Platform detection for vwc.
"""

import subprocess
import platform as py_platform


def detect_platform():
    """
    Detect platform for wc behavior differences.

    Returns:
        str: Platform identifier ("gnu", "bsd", "linux", "windows", or "unknown")
    """
    system = py_platform.system()
    if system == "Linux":
        # Check if it's GNU coreutils
        try:
            version = subprocess.check_output(["wc", "--version"], text=True)
            if "GNU coreutils" in version:
                return "gnu"
        except:  # noqa: E722
            pass
        return "linux"
    elif system == "Darwin":
        return "bsd"
    elif system == "FreeBSD":
        return "bsd"
    elif system == "Windows":
        return "windows"
    return "unknown"
