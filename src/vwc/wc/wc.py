# src/vwc/wc/wc.py
"""
Base class for word count (wc) implementations.
This is the base UNIX implementation.
"""

import argparse
import os
import platform
import sys
import time


class WC:
    """
    Usage: wc [-cmlwL] [FILE]...

    Count lines, words, and bytes for FILEs (or stdin)
    """

    def __init__(self):
        self.platform = platform.system()
        self.parser = self.create_parser()
        self.exit_code = 0

    def create_parser(self) -> argparse.ArgumentParser:
        """Create a basic argument parser with core options."""
        parser = argparse.ArgumentParser(
            description=self.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, add_help=False
        )
        # Core options common to all wc implementations
        parser.add_argument("-c", action="store_true", dest="bytes", help="print the byte counts")
        parser.add_argument("-m", action="store_true", dest="chars", help="print the character counts")
        parser.add_argument("-l", action="store_true", dest="lines", help="print the newline counts")
        parser.add_argument("-w", action="store_true", dest="words", help="print the word counts")

        # Platform-specific arguments added by subclasses
        self.add_platform_args(parser)

        parser.add_argument("files", nargs="*", help="files to process")
        return parser

    def add_platform_args(self, parser):
        """Add platform-specific arguments - overridden by subclasses"""
        # Default help option - most basic implementation
        parser.add_argument("-h", action="help", help="display help and exit")

    def parse_args(self, argv):
        """Parse command line arguments"""
        self.args = self.parser.parse_args(argv)

    def process_line(self, line, args):
        """Process a single line and return counts based on requested options."""
        counts = []

        # Only calculate what's needed based on args
        if args.lines:
            counts.append(1)  # Always 1 line per line

        if args.words:
            # Only decode and split if we need word count
            try:
                text = line.decode("utf-8")
            except UnicodeDecodeError:
                text = line.decode("latin-1")
            counts.append(len(text.split()))

        if args.bytes:
            counts.append(len(line))  # Byte count

        if args.chars:
            # Only decode if not already done for words
            if not args.words:
                try:
                    text = line.decode("utf-8")
                except UnicodeDecodeError:
                    text = line.decode("latin-1")
            counts.append(len(text))

        if getattr(args, "max_line_length", False):
            # Only decode if not already done
            if not (args.words or args.chars):
                try:
                    text = line.decode("utf-8")
                except UnicodeDecodeError:
                    text = line.decode("latin-1")
            # TODO: This is simplistic - real max line length should consider
            # display width, tabs, etc. according to platform
            counts.append(len(text))

        return counts

    def print_line(self, counts, filename, file=sys.stdout):
        """Format and print count line for a file."""
        # Format counts with proper spacing
        output = ""
        for count in counts:
            if count is not None:
                output += f"{count:8d} "

        # Add filename if not empty
        if filename:
            output += filename

        print(output, file=file)

    def show_progress(self, counts, filename):
        """Show progress to stderr if it's a TTY."""
        if not sys.stderr.isatty():
            return

        # Clear current line and move cursor to beginning
        sys.stderr.write("\r\033[K")
        self.print_line(counts, filename, file=sys.stderr)

        sys.stderr.flush()

    def print_totals(self, counts):
        """Print total counts."""
        if len(self.args.files) > 1:
            self.print_line(counts, "total")

    def handle_error(self, error, filename):
        """Handle file error and report it."""
        exe = os.path.basename(sys.argv[0])
        sys.stderr.write(f"{exe}: {filename}: {error.strerror}\n")
        self.set_status(1)  # Set non-zero exit status

    def set_status(self, code):
        """Set the exit status - generic implementation."""
        self.exit_code = code
        return code

    def get_files(self, args):
        """
        Get file objects to process based on arguments as a generator.
        UNIX implementation treats '-' as a literal file name.
        """
        # If no files specified, use stdin
        if not args.files:
            yield ("", sys.stdin.buffer)  # Empty name for stdin
            return

        # Process each file argument
        for filename in args.files:
            try:
                # Open in binary mode to handle all types of files
                # In UNIX, '-' is just a regular file name
                file_obj = open(filename, "rb")
                yield (filename, file_obj)
            except OSError as e:
                self.handle_error(e, filename)

    def run(self):
        """Process files and print counts."""
        self.exit_code = 0
        args = self.args

        # If no options specified, show default set (lines, words, bytes)
        if not (args.bytes or args.chars or args.lines or args.words or getattr(args, "max_line_length", False)):
            args.lines = args.words = args.bytes = True

        # Get file generator
        file_gen = self.get_files(args)

        # Initialize totals for each count type
        totals = [0] * len(self.process_line(b"", args))
        for filename, file_obj in file_gen:
            try:
                counts = self.process_file(filename, file_obj, args)
                totals = [totals[i] + counts[i] for i in range(len(counts))]

                self.print_line(counts, filename)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                self.handle_error(e, filename)

        self.print_totals(totals)

        return self.exit_code

    def process_file(self, filename, file_obj, args):
        """Process a file and return (filename, counts)."""
        # Get the empty counts structure to understand what counts we're calculating
        empty_counts = self.process_line(b"", args)
        file_counts = [0] * len(empty_counts)

        # Track timing for progress updates
        last_update = time.time()

        # Process file line by line
        for line in file_obj:
            # Process the line
            line_counts = self.process_line(line, args)

            # Update file counts
            for i, count in enumerate(line_counts):
                file_counts[i] += count

            # Show progress every ~200ms if stderr is a TTY
            current_time = time.time()
            if current_time - last_update >= 0.2:
                self.show_progress(file_counts, filename)
                last_update = current_time

        # Clear progress line before returning
        if sys.stderr.isatty():
            sys.stderr.write("\r\033[K")
            sys.stderr.flush()

        # Close file if not stdin
        if filename != "":
            file_obj.close()

        return file_counts
