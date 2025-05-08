# src/vwc/wc/gnu.py
import argparse
import sys

from .wc import WC


class GNU(WC):
    """
    wc - print newline, word, and byte counts for each file

    Usage: wc [OPTION]... [FILE]...
    or: wc [OPTION]... --files0-from=F

    Print newline, word, and byte counts for each FILE, and a total line if
    more than one FILE is specified. A word is a non-zero-length sequence of
    characters delimited by white space.

    With no FILE, or when FILE is -, read standard input.
    """

    def add_platform_args(self, parser):
        """GNU-specific arguments."""
        # GNU supports -L with a long option
        parser.add_argument("-L", "--max-line-length", action="store_true", help="print the length of the longest line")

        # GNU-specific options
        parser.add_argument(
            "--files0-from", metavar="F", help="read input from files specified by NUL-separated names in file F"
        )
        parser.add_argument(
            "--total", choices=["auto", "always", "only", "never"], default="auto", help="when to print a total line"
        )

        # GNU-style help and version
        parser.add_argument("--help", action="help", help="display help and exit")
        parser.add_argument("--version", action="store_true", help="output version information and exit")

        # GNU long-form aliases
        parser.add_argument("--bytes", action="store_true", dest="bytes", help=argparse.SUPPRESS)
        parser.add_argument("--chars", action="store_true", dest="chars", help=argparse.SUPPRESS)
        parser.add_argument("--lines", action="store_true", dest="lines", help=argparse.SUPPRESS)
        parser.add_argument("--words", action="store_true", dest="words", help=argparse.SUPPRESS)

    def get_files(self, args):
        """Handle file processing with GNU-specific behavior."""
        # Handle --files0-from option
        if getattr(args, "files0_from", None):
            try:
                source = sys.stdin if args.files0_from == "-" else open(args.files0_from, "r")
                filenames = source.read().split("\0")
                if source != sys.stdin:
                    source.close()

                for filename in filter(None, filenames):
                    try:
                        yield (filename, open(filename, "rb"))
                    except OSError as e:
                        self.handle_error(e, filename)
                return
            except Exception as e:
                self.handle_error(e, args.files0_from)
                return

        # Handle regular file arguments or stdin
        if not args.files:
            yield ("", sys.stdin.buffer)
            return

        for filename in args.files:
            try:
                if filename == "-":
                    yield (filename, sys.stdin.buffer)
                else:
                    yield (filename, open(filename, "rb"))
            except OSError as e:
                self.handle_error(e, filename)

    def print_totals(self, counts):
        """Print total counts."""

        always_print = self.args.total in ("always", "only")
        never_print = self.args.total == "never"
        has_files = len(self.args.files) > 1
        should_print = always_print or (has_files and not never_print)

        if should_print:
            self.print_line(counts, "total")

    def print_line(self, counts, filename, file=sys.stdout):
        """Format output with GNU-specific formatting."""
        # Handle single count with no leading space (GNU extension)
        if len(counts) == 1:
            output = f"{counts[0]}"
            if filename:
                output += f" {filename}"
        else:
            # Standard formatting for multiple counts
            output = " ".join(f"{count:7d}" for count in counts)
            if filename:
                output += f" {filename}"

        print(output, file=file)
