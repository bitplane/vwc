# src/vwc/wc/busybox.py
import sys

from .linux import Linux


class BusyBox(Linux):
    """
    wc - word, line, and byte count

    Usage: wc [-cmlwL] [FILE]...

    Count lines, words, and bytes for FILEs (or stdin)
    """

    def add_platform_args(self, parser):
        """BusyBox-specific arguments."""
        # BusyBox supports -L
        parser.add_argument("-L", action="store_true", dest="max_line_length", help="print longest line length")

        # BusyBox only supports --help (not -h)
        parser.add_argument("--help", action="help", help="display help and exit")

    def print_line(self, counts, filename, file=sys.stdout):
        """Format and print count line for a file with BusyBox formatting."""
        if len(counts) == 1:
            # When only one count is printed, no padding
            output = f"{counts[0]}"
            if filename:
                output += f" {filename}"
        else:
            # BusyBox format: 9-character fields right-justified with a space between fields
            output = " ".join(f"{count:9d}" for count in counts)

            # Add filename if not empty
            if filename:
                output += f" {filename}"

        print(output, file=file, flush=True)
