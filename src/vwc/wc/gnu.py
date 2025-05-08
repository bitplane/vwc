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
        """
        GNU-specific file handling - handles '-' as stdin and --files0-from option.
        """
        # Handle --files0-from option if specified
        if hasattr(args, "files0_from") and args.files0_from:
            try:
                # Open file with NUL-terminated filenames
                if args.files0_from == "-":
                    filenames = sys.stdin.read().split("\0")
                else:
                    with open(args.files0_from, "r") as f:
                        filenames = f.read().split("\0")

                # Process each filename
                for filename in filenames:
                    if not filename:  # Skip empty names (trailing NUL)
                        continue
                    try:
                        file_obj = open(filename, "rb")
                        yield (filename, file_obj)
                    except OSError as e:
                        self.handle_error(e, filename)

                return
            except Exception as e:
                self.handle_error(e, args.files0_from)
                return

        # If no files specified, use stdin
        if not args.files:
            yield ("", sys.stdin.buffer)  # Empty name for stdin
            return

        # Process each file argument
        for filename in args.files:
            if filename == "-":
                yield ("", sys.stdin.buffer)  # Empty name for stdin
            else:
                try:
                    # Open in binary mode to handle all types of files
                    file_obj = open(filename, "rb")
                    yield (filename, file_obj)
                except OSError as e:
                    self.handle_error(e, filename)

    def run(self, args):
        """Process files with GNU-specific behavior for --total."""
        # Handle --total=only separately
        if args.total == "only":
            return self.run_total_only(args)

        # Normal processing
        self.exit_code = 0

        # If no options specified, show default set (lines, words, bytes)
        if not (args.bytes or args.chars or args.lines or args.words or args.max_line_length):
            args.lines = args.words = args.bytes = True

        # Get files to process
        files = self.get_files(args)

        # Process each file
        file_results = []
        for filename, file_obj in files:
            try:
                file_results.append(self.process_file(filename, file_obj, args))
            except KeyboardInterrupt:
                raise
            except Exception as e:
                self.handle_error(e, filename)

        # Print individual file results
        for filename, counts in file_results:
            self.print_line(counts, filename)

        # Print totals based on --total option
        should_print_total = False
        if args.total == "auto":
            should_print_total = len(file_results) > 1
        elif args.total == "always":
            should_print_total = True
        elif args.total == "never":
            should_print_total = False

        if should_print_total and file_results:
            # Sum up all counts
            totals = [0] * len(file_results[0][1])
            for _, counts in file_results:
                for i, count in enumerate(counts):
                    totals[i] += count

            self.print_summary(totals)

        return self.exit_code

    def run_total_only(self, args):
        """Run with --total=only to print only the total."""
        self.exit_code = 0

        # If no options specified, show default set (lines, words, bytes)
        if not (args.bytes or args.chars or args.lines or args.words or args.max_line_length):
            args.lines = args.words = args.bytes = True

        # Get files to process
        files = self.get_files(args)

        # Process all files but only accumulate totals
        empty_counts = self.process_line(b"", args)
        totals = [0] * len(empty_counts)

        for filename, file_obj in files:
            try:
                for line in file_obj:
                    line_counts = self.process_line(line, args)
                    for i, count in enumerate(line_counts):
                        totals[i] += count

                # Close file if not stdin
                if filename != "":
                    file_obj.close()
            except Exception as e:
                self.handle_error(e, filename)

        # Print only the totals, with no label
        self.print_line(totals, "")

        return self.exit_code

    def print_line(self, counts, filename, file=sys.stdout):
        """Format and print count line for a file with GNU formatting."""
        # GNU format: 7-character fields right-justified
        # If only one count, no padding (GNU extension)
        if len(counts) == 1:
            output = f"{counts[0]}"
        else:
            output = ""
            for count in counts:
                if count is not None:
                    output += f"{count:7d} "

        # Add filename if not empty
        if filename:
            output += f" {filename}" if len(counts) == 1 else filename

        print(output, file=file)
