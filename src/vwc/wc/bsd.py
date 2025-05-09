# src/vwc/wc/bsd.py
import sys

from .wc import WC


class BSD(WC):
    """
    wc - count lines, words, characters, and bytes

    Usage: wc [-clmwL] [file ...]

    Count lines, words, characters, and bytes for each input file.
    With no file, or when file is -, read standard input.
    """

    def add_platform_args(self, parser):
        """BSD-specific arguments."""
        # BSD supports -L but without long option
        parser.add_argument(
            "-L", action="store_true", dest="max_line_length", help="print the length of the longest line in bytes"
        )

        # BSD-style help
        parser.add_argument("-h", action="help", help="display help and exit")

    def print_line(self, counts, filename, file=sys.stdout):
        """Format and print count line for a file with BSD formatting."""
        # BSD format: 7-character fields right-justified
        output = ""
        for count in counts:
            if count is not None:
                output += f"{count:7d} "

        # Add filename if not empty
        if filename:
            output += filename

        print(output, file=file, flush=True)
