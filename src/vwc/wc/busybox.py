# src/vwc/wc/busybox.py
import sys

from .linux import Linux
from .wc import WC


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

    def char_width(self, char):
        # BusyBox wc measures printable ASCII for -L; multibyte characters
        # do not advance its display column.
        return 1 if " " <= char <= "~" else 0

    def count_words(self, line, text):
        words = 0
        in_word = False
        for byte in line:
            if byte in (9, 10, 11, 12, 13, 32):
                in_word = False
            elif 33 <= byte <= 126 and not in_word:
                words += 1
                in_word = True
        return words

    def handle_error(self, error, filename):
        if isinstance(error, IsADirectoryError):
            # BusyBox writes the diagnostic before the zero-count row.
            WC.handle_error(self, error, filename)
            self.reset_counts()
            self.print_counts(filename)
        else:
            super().handle_error(error, filename)

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
