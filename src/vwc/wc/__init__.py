# src/vwc/wc/__init__.py - update this file
import platform
import subprocess
from .wc import WC


def get_wc(platform_=platform.system()) -> WC:
    """Get the appropriate platform implementation."""
    # Check for BusyBox
    if platform_ == "Linux":
        # Try to detect BusyBox
        try:
            output = subprocess.check_output(["wc", "--help"], stderr=subprocess.STDOUT, text=True)
            if "BusyBox" in output:
                from vwc.wc.busybox import BusyBox

                return BusyBox()
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        # Default to GNU on Linux
        from vwc.wc.gnu import GNU

        return GNU()
    elif platform_ in ("BSD", "Darwin"):
        from vwc.wc.bsd import BSD

        return BSD()
    else:
        # Generic implementation
        return WC()


__all__ = ["get_wc", "WC"]
