# src/vwc/main.py - update this file
"""
Main entry point for vwc.
"""

import signal
import sys

from vwc.wc import get_wc


def main():
    """Main entry point."""
    # Handle broken pipe gracefully
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    # Handle other common signals
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda s, _f: sys.exit(128 + s))

    try:
        wc = get_wc()
        wc.parse_args(sys.argv[1:])
        code = wc.run()
        return code
    except KeyboardInterrupt:
        sys.stderr.write("\n")
        return 130  # Standard exit code for SIGINT


if __name__ == "__main__":
    sys.exit(main())
