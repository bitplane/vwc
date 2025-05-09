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

import wcwidth


class WC:
    """
    Usage: wc [-cmlwL] [FILE]...

    Count lines, words, and bytes for FILEs (or stdin)
    """

    def __init__(self):
        # Configuration state
        self.platform = platform.system()
        self.parser = self.create_parser()
        self.exit_code = 0
        self.column_width = 7  # Default column width
        self.args = None

        # Reset current file count and total counts
        self.reset_counts()
        self.reset_totals()

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

    def reset_counts(self):
        """Reset file-specific counts."""
        self.lines = 0
        self.words = 0
        self.bytes = 0
        self.chars = 0
        self.max_width = 0

    def reset_totals(self):
        """Reset total counts."""
        self.total_lines = 0
        self.total_words = 0
        self.total_bytes = 0
        self.total_chars = 0
        self.total_max_width = 0

    def process_line(self, line):
        """Process a single line and update instance state."""
        # Calculate all requested counts
        if self.args.lines:
            self.lines += 1

        # Decode for word and character counts
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError:
            text = line.decode("latin-1")

        if self.args.words:
            self.words += len(text.split())

        if self.args.bytes:
            self.bytes += len(line)

        if self.args.chars:
            self.chars += len(text)

        if getattr(self.args, "max_line_length", False):
            # Strip newline for display width calculation
            text_no_nl = text.rstrip("\n")
            # Calculate display width according to POSIX rules
            display_width = self.get_display_width(text_no_nl)
            # Update max_width if this line is longer
            self.max_width = max(self.max_width, display_width)

    def get_counts_array(self, use_totals=False):
        """Get current counts as an array in the standard order."""
        counts = []

        if self.args.lines:
            counts.append(self.total_lines if use_totals else self.lines)

        if self.args.words:
            counts.append(self.total_words if use_totals else self.words)

        if self.args.bytes:
            counts.append(self.total_bytes if use_totals else self.bytes)

        if self.args.chars:
            counts.append(self.total_chars if use_totals else self.chars)

        if getattr(self.args, "max_line_length", False):
            counts.append(self.total_max_width if use_totals else self.max_width)

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

    def print_totals(self, file=sys.stdout):
        """Print total counts."""
        if len(self.args.files) > 1:
            counts = self.get_counts_array(use_totals=True)
            self.print_line(counts, "total", file)

    def print_counts(self, filename, file=sys.stdout):
        """Print counts for the current file."""
        counts = self.get_counts_array()
        self.print_line(counts, filename, file)

    def print_progress(self, filename):
        """Show progress to stderr if it's a TTY."""
        if not sys.stderr.isatty():
            return

        # Clear current line and move cursor to beginning
        sys.stderr.write("\r\033[K")
        counts = self.get_counts_array()
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

    def get_file_names(self):
        """Files to process, can be overriden"""
        return self.args.files or [""]

    def get_files(self):
        """
        Get file objects to process based on arguments as a generator.
        """
        names = self.get_file_names()
        # Process each file argument
        for filename in names:
            try:
                yield filename, self.open_file(filename)
            except OSError as e:
                self.handle_error(e, filename)

    def open_file(self, filename):
        # Open in binary mode to handle all types of files
        # In UNIX, '-' is just a regular file name
        if not filename or filename == "-":
            return sys.stdin.buffer
        return open(filename, "rb")

    def run(self):
        """Process files and print counts."""
        self.exit_code = 0
        args = self.args

        # If no options specified, show default set (lines, words, bytes)
        if not (args.bytes or args.chars or args.lines or args.words or getattr(args, "max_line_length", False)):
            args.lines = args.words = args.bytes = True

        # Get file generator
        file_gen = self.get_files()

        # Reset total counters
        self.reset_totals()

        for filename, file_obj in file_gen:
            try:
                # Process the file
                self.process_file(filename, file_obj)

                # Print counts for this file
                self.print_counts(filename)

                # Update totals from current file counts
                self.update_totals()

            except KeyboardInterrupt:
                raise
            except Exception as e:
                self.handle_error(e, filename)

        # Print totals if needed
        self.print_totals()

        return self.exit_code

    def update_totals(self):
        """Update total counts from current file counts."""
        if self.args.lines:
            self.total_lines += self.lines
        if self.args.words:
            self.total_words += self.words
        if self.args.bytes:
            self.total_bytes += self.bytes
        if self.args.chars:
            self.total_chars += self.chars
        if getattr(self.args, "max_line_length", False):
            # For max line length, take the maximum value
            self.total_max_width = max(self.total_max_width, self.max_width)

    def process_file(self, filename, file_obj):
        """Process a file and update instance state."""
        # Reset counts for this file
        self.reset_counts()

        # Track timing for progress updates
        last_update = time.time()

        # Process file line by line
        for line in file_obj:
            # Process the line and update state
            self.process_line(line)

            # Show progress every ~200ms if stderr is a TTY
            current_time = time.time()
            if current_time - last_update >= 0.2:
                self.print_progress(filename)
                last_update = current_time

        # Clear progress line before returning
        if sys.stderr.isatty():
            sys.stderr.write("\r\033[K")
            sys.stderr.flush()

        # Close file if not stdin
        if filename and file_obj != sys.stdin.buffer:
            file_obj.close()
