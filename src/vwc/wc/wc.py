import argparse
import os
import platform
import sys
import time

import wcwidth


class WC:
    """
    Usage: wc [-cmlwL] [FILE]...

    Count lines, words, and bytes for FILEs (or stdin)
    """

    def __init__(self):
        self.platform = platform.system()
        self.parser = self.create_parser()
        self.exit_code = 0
        self.counts = None
        self.totals = None
        self.column_width = 7  # Default column width

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

    def get_display_width(self, text):
        """Calculate the display width of text according to POSIX rules."""
        # Use wcwidth to calculate display width, handling CJK, emojis, etc.
        # Expand tabs to 8 spaces as per POSIX standard
        text_expanded = text.expandtabs(8)
        width = 0

        # Calculate width character by character
        for char in text_expanded:
            # wcwidth returns -1 for control characters, count them as 0
            char_width = wcwidth.wcwidth(char)
            if char_width >= 0:
                width += char_width

        return width

    def process_line(self, line):
        """Process a single line and return counts based on requested options."""
        counts = []

        # Skip processing for empty line (used for initialization)
        if not line:
            # Add placeholders for all requested counts
            if self.args.lines:
                counts.append(0)
            if self.args.words:
                counts.append(0)
            if self.args.bytes:
                counts.append(0)
            if self.args.chars:
                counts.append(0)
            if getattr(self.args, "max_line_length", False):
                counts.append(0)
            return counts

        # Calculate all requested counts
        if self.args.lines:
            counts.append(1)  # Always 1 line per line

        # Decode for word and character counts
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError:
            text = line.decode("latin-1")

        if self.args.words:
            counts.append(len(text.split()))

        if self.args.bytes:
            counts.append(len(line))  # Byte count

        if self.args.chars:
            counts.append(len(text))  # Character count

        if getattr(self.args, "max_line_length", False):
            # Strip newline for display width calculation
            text_no_nl = text.rstrip("\n")
            # Calculate display width according to POSIX rules
            display_width = self.get_display_width(text_no_nl)
            counts.append(display_width)

        return counts

    def print_line(self, counts, filename, file=sys.stdout):
        """Format and print count line for a file, totals or preview."""
        # Format counts with proper spacing
        output = ""
        for count in counts:
            if count is not None:
                output += f"{count:8d} "

        # Add filename if not empty
        if filename:
            output += filename

        print(output, file=file, flush=True)

    def print_totals(self, counts):
        """Print total counts."""
        if len(self.args.files) > 1:
            self.print_line(counts, "total")

    def print_counts(self, counts, filename, file=sys.stdout):
        """Print counts for a file."""
        self.print_line(counts, filename, file)

    def print_progress(self, counts, filename):
        """Show progress to stderr if it's a TTY."""
        if not sys.stderr.isatty():
            return

        # Clear current line and move cursor to beginning
        sys.stderr.write("\r\033[K")
        self.print_line(counts, filename, file=sys.stderr)
        # Move up a line to overwrite next time
        sys.stderr.write("\033[F")

        sys.stderr.flush()

    def handle_error(self, error, filename):
        """Handle file error and report it."""
        exe = os.path.basename(sys.argv[0])
        sys.stderr.write(f"{exe}: {filename}: {error.strerror}\n")
        self.set_status(1)  # Set non-zero exit status

    def set_status(self, code):
        """Set the exit status - generic implementation."""
        self.exit_code = code
        return code

    def get_files(self):
        """
        Get file objects to process based on arguments as a generator.
        UNIX implementation treats '-' as a literal file name.
        """
        # If no files specified, use stdin
        if not self.args.files:
            yield ("", sys.stdin.buffer)  # Empty name for stdin
            return

        # Process each file argument
        for filename in self.args.files:
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
        file_gen = self.get_files()

        # Initialize totals for each count type
        totals = [0] * len(self.process_line(b""))
        for filename, file_obj in file_gen:
            try:
                counts = self.process_file(filename, file_obj)

                # Update totals - for max_line_length, take the max rather than sum
                has_max_line = getattr(self.args, "max_line_length", False)
                for i in range(len(counts)):
                    # For the max_line_length field, take max instead of sum
                    if has_max_line and i == len(counts) - 1:
                        totals[i] = max(totals[i], counts[i])
                    else:
                        totals[i] += counts[i]

                self.print_counts(counts, filename)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                self.handle_error(e, filename)

        self.print_totals(totals)

        return self.exit_code

    def process_file(self, filename, file_obj):
        """Process a file and return (filename, counts)."""
        # Get the empty counts structure to understand what counts we're calculating
        empty_counts = self.process_line(b"")
        file_counts = [0] * len(empty_counts)

        # Flag for max line length position
        has_max_line = getattr(self.args, "max_line_length", False)
        max_line_idx = len(file_counts) - 1 if has_max_line else -1

        # Track timing for progress updates
        last_update = time.time()

        # Process file line by line
        for line in file_obj:
            # Process the line
            line_counts = self.process_line(line)

            # Update file counts
            for i, count in enumerate(line_counts):
                if has_max_line and i == max_line_idx:
                    # For max line length, take the maximum
                    file_counts[i] = max(file_counts[i], count)
                else:
                    # For other counts, sum them
                    file_counts[i] += count

            # Show progress every ~200ms if stderr is a TTY
            current_time = time.time()
            if current_time - last_update >= 0.2:
                self.print_progress(file_counts, filename)
                last_update = current_time

        # Clear progress line before returning
        if sys.stderr.isatty():
            sys.stderr.write("\r\033[K")
            sys.stderr.flush()

        # Close file if not stdin
        if filename != "":
            file_obj.close()

        return file_counts
