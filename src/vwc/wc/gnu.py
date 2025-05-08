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
                    yield ("", sys.stdin.buffer)
                else:
                    yield (filename, open(filename, "rb"))
            except OSError as e:
                self.handle_error(e, filename)

    def run(self, args):
        """Process files with GNU-specific behavior."""
        # Handle --total=only as a special case
        if getattr(args, "total", "auto") == "only":
            return self._process_total_only(args)

        # Normal processing
        self.exit_code = 0

        # Set default options if none specified
        if not any(getattr(args, opt, False) for opt in ["bytes", "chars", "lines", "words", "max_line_length"]):
            args.lines = args.words = args.bytes = True

        # Process files and collect results
        file_results = []
        for filename, file_obj in self.get_files(args):
            try:
                file_results.append(self.process_file(filename, file_obj, args))
            except KeyboardInterrupt:
                raise
            except Exception as e:
                self.handle_error(e, filename)

        # Print individual file results
        for result in file_results:
            self.print_line(*result)

        # Handle totals based on --total option
        total_mode = getattr(args, "total", "auto")
        should_print_total = total_mode == "always" or (total_mode == "auto" and len(file_results) > 1)

        if should_print_total and file_results:
            # Sum all counts and print total
            totals = [sum(counts[i] for _, counts in file_results) for i in range(len(file_results[0][1]))]
            self.print_summary(totals)

        return self.exit_code

    def _process_total_only(self, args):
        """Process with --total=only to print only the total."""
        self.exit_code = 0

        # Set default options if none specified
        if not any(getattr(args, opt, False) for opt in ["bytes", "chars", "lines", "words", "max_line_length"]):
            args.lines = args.words = args.bytes = True

        # Get structure of counts from an empty line
        empty_counts = self.process_line(b"", args)
        totals = [0] * len(empty_counts)

        # Process all files, accumulating totals
        for filename, file_obj in self.get_files(args):
            try:
                for line in file_obj:
                    line_counts = self.process_line(line, args)
                    for i, count in enumerate(line_counts):
                        totals[i] += count

                if filename:  # Close if not stdin
                    file_obj.close()
            except Exception as e:
                self.handle_error(e, filename)

        # Print only the totals with no label
        self.print_line(totals, "")
        return self.exit_code

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
