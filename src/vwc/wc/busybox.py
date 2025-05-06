# src/vwc/wc/busybox.py - create this file
import sys
from .wc import WC


class BusyBox(WC):
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

    def get_files(self, args):
        """
        BusyBox-specific file handling - treats '-' as stdin.
        """
        files = []

        # If no files specified, use stdin
        if not args.files:
            files.append(("", sys.stdin.buffer))  # Empty name for stdin
            return files

        # Process each file argument
        for filename in args.files:
            if filename == "-":
                files.append(("-", sys.stdin.buffer))  # called - if explicitly added
            else:
                try:
                    # Open in binary mode to handle all types of files
                    file_obj = open(filename, "rb")
                    files.append((filename, file_obj))
                except OSError as e:
                    self.handle_error(e, filename)

        return files

    def print_line(self, counts, filename, file=sys.stdout):
        """Format and print count line for a file with BusyBox formatting."""
        # BusyBox format: 9-character fields right-justified
        output = ""
        for count in counts:
            if count is not None:
                output += f"{count:9d} "

        # Add filename if not empty
        if filename:
            output += filename

        print(output, file=file)
