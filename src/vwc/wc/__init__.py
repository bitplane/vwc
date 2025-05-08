import os
import platform
from .wc import WC


def get_wc() -> WC:
    """Get the appropriate platform implementation by checking PATH."""
    system = platform.system()

    if system == "Linux":
        # Check all directories in PATH
        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        for directory in path_dirs:
            wc_path = os.path.join(directory, "wc")
            if os.path.islink(wc_path):
                try:
                    target = os.readlink(wc_path)
                    if os.path.basename(target) == "busybox" or "busybox" in target:
                        from vwc.wc.busybox import BusyBox

                        return BusyBox()
                except (OSError, IOError):
                    pass

        # Default to GNU on Linux
        from vwc.wc.gnu import GNU

        return GNU()

    elif system in ("FreeBSD", "OpenBSD", "NetBSD", "Darwin"):
        from vwc.wc.bsd import BSD

        return BSD()
    else:
        # Default to GNU for unknown platforms
        from vwc.wc.gnu import GNU

        return GNU()


__all__ = ["get_wc", "WC"]
