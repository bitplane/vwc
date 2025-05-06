"""
Command-line interface for vwc.
"""

import argparse
import signal
import sys
from .format import write


# Command-line help text
HELP_TEXT = """
vwc — A GNU-compatible `wc` implementation with visual preview.

Usage: vwc [OPTION]... [FILE]...
  or:  vwc [OPTION]... --files0-from=F

Print newline, word, and byte counts for each FILE, and a total line if
more than one FILE is specified. A word is a non-zero-length sequence of
printable characters delimited by white space.

With no FILE, or when FILE is -, read standard input.

Live preview of counts is shown every 200ms to stderr if stderr is a TTY.

Options:
  -c, --bytes            print the byte counts
  -m, --chars            print the character counts
  -l, --lines            print the newline counts
  -w, --words            print the word counts
  -L, --max-line-length  print the maximum display width
      --files0-from=F    read input from the files specified by
                         NUL-terminated names in file F;
                         If F is - then read names from standard input
      --total=WHEN       when to print a line with total counts;
                         WHEN can be: auto, always, only, never
      --help             display this help and exit
      --version          print version information and exit
"""


def parse_args(argv):
    """Parse command line arguments."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("-c", "--bytes", action="store_true", dest="bytes")
    p.add_argument("-m", "--chars", action="store_true", dest="chars")
    p.add_argument("-l", "--lines", action="store_true", dest="lines")
    p.add_argument("-w", "--words", action="store_true", dest="words")
    p.add_argument("-L", "--max-line-length", action="store_true", dest="max_line_length")
    p.add_argument("--files0-from")
    p.add_argument("--total", choices=["auto", "always", "only", "never"], default="auto")
    p.add_argument("--help", action="store_true")
    p.add_argument("--version", action="store_true")
    p.add_argument("files", nargs="*")
    return p.parse_args(argv)


def main():
    """Main entry point for the command-line interface."""
    # Import here to avoid circular imports
    from .app import run_wc

    # Handle broken pipe gracefully
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    # Handle other common signals
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda s, f: sys.exit(128 + s))

    try:
        sys.exit(run_wc(sys.argv[1:]))
    except KeyboardInterrupt:
        write("", to_err=True)
        sys.exit(130)  # Standard exit code for SIGINT
