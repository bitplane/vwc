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
        if self.use_padding():
            # BusyBox format: 9-character fields right-justified with a space between fields
            output = " ".join(f"{count:9d}" for count in counts)
        else:
            output = f"{counts[0]}"

        # Add filename if not empty
        if filename:
            output += f" {filename}"

        print(output, file=file, flush=True)

    def use_padding(self):
        """
        BusyBox-specific padding rules.
        BusyBox uses padding for -L only when processing multiple files.
        """
        has_max_line_length = getattr(self.args, "max_line_length", False)
        has_multiple_files = len(self.args.files) > 1
        columns = ("lines", "words", "bytes", "chars")
        column_count = sum(1 for arg in columns if hasattr(self.args, arg) and getattr(self.args, arg))

        return column_count > 1 or (has_max_line_length and has_multiple_files)
