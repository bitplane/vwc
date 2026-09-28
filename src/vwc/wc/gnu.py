# src/vwc/wc/gnu.py
import argparse
import codecs
import os
import re
import stat
import subprocess
import sys

from .linux import Linux


class GNU(Linux):
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

    def count_chars(self, line, text):
        if codecs.lookup(self.encoding).name == "ascii":
            return len(line)
        return len(line.decode(self.encoding, errors="ignore"))

    def count_words(self, line, text):
        if not hasattr(self, "legacy_word_count"):
            version = self.native_gnu_version()
            self.legacy_word_count = version is not None and version < (9, 5)
        if self.legacy_word_count:
            return len(line.decode(self.encoding, errors="ignore").split())
        if codecs.lookup(self.encoding).name == "ascii":
            # Modern GNU treats 0xa0 as whitespace even in the C locale.
            return self.count_c_words(line)
        return len(text.split())

    def accelerated_word_mode(self):
        if not hasattr(self, "legacy_word_count"):
            version = self.native_gnu_version()
            self.legacy_word_count = version is not None and version < (9, 5)
        if codecs.lookup(self.encoding).name == "ascii":
            return "gnu_legacy_c" if self.legacy_word_count else "gnu_c"
        if codecs.lookup(self.encoding).name == "utf-8":
            return "unicode_ignore" if self.legacy_word_count else "unicode"
        return None

    @staticmethod
    def native_gnu_version():
        """Query the installed wc once; GNU changed invalid-byte word counts in 9.5."""
        own_executable = os.path.realpath(sys.argv[0])
        for directory in os.environ.get("PATH", "").split(os.pathsep):
            candidate = os.path.join(directory or ".", "wc")
            if not os.access(candidate, os.X_OK) or os.path.realpath(candidate) == own_executable:
                continue
            try:
                result = subprocess.run([candidate, "--version"], capture_output=True, timeout=2, check=False)
            except (OSError, subprocess.TimeoutExpired):
                continue
            match = re.search(rb"wc \(GNU coreutils\) (\d+)\.(\d+)", result.stdout)
            if match:
                return int(match[1]), int(match[2])
        return None

    @staticmethod
    def count_c_words(line):
        in_word = False
        words = 0
        for byte in line:
            if byte in (9, 10, 11, 12, 13, 32, 160):
                in_word = False
            elif not in_word:
                words += 1
                in_word = True
        return words

    def get_file_names(self):
        """Return list of file names from --files0-from or args.files."""
        args = self.args
        self.file_source_error = False

        if args.files0_from is not None:
            try:
                if args.files:
                    exe = os.path.basename(sys.argv[0])
                    sys.stderr.write(
                        f"{exe}: extra operand '{args.files[0]}'\n"
                        "file operands cannot be combined with --files0-from\n"
                        f"Try '{exe} --help' for more information.\n"
                    )
                    raise SystemExit(1)
                if args.files0_from == "-":
                    data = sys.stdin.buffer.read()
                else:
                    with open(args.files0_from, "rb") as source:
                        data = source.read()
                raw_names = data.split(b"\0")
                if not data or data.endswith(b"\0"):
                    raw_names.pop()
                filenames = [os.fsdecode(name) if name else None for name in raw_names]
                self.file_count = len(filenames)
                self.set_column_width(filenames)
                return filenames
            except OSError as e:
                exe = os.path.basename(sys.argv[0])
                sys.stderr.write(f"{exe}: cannot open '{args.files0_from}' for reading: {e.strerror}\n")
                self.set_status(1)
                self.file_source_error = True
                return []

        file_names = args.files or [""]
        self.file_count = len(file_names)
        self.set_column_width(file_names)

        return file_names

    def handle_empty_name(self, index):
        exe = os.path.basename(sys.argv[0])
        sys.stderr.write(f"{exe}: {self.args.files0_from}:{index}: invalid zero-length file name\n")
        self.set_status(1)

    def validate_filename(self, filename):
        if self.args.files0_from == "-" and filename == "-":
            exe = os.path.basename(sys.argv[0])
            sys.stderr.write(f"{exe}: when reading file names from stdin, no file name of '-' allowed\n")
            self.set_status(1)
            return False
        return True

    def print_totals(self, file=sys.stdout):
        """Print total counts."""
        if self.file_source_error:
            return
        always_print = self.args.total in ("always", "only")
        never_print = self.args.total == "never"
        has_files = self.file_count > 1
        should_print = always_print or (has_files and not never_print)

        if should_print:
            name = "" if self.args.total == "only" else "total"
            counts = self.get_counts_array(use_totals=True)
            self.print_line(counts, name, file)

    def print_counts(self, filename, file=sys.stdout):
        """Print counts for a file."""
        if self.args.total == "only":
            return

        counts = self.get_counts_array()
        self.print_line(counts, filename, file)

    def print_line(self, counts, filename, file=sys.stdout):
        """GNU-specific line printing using width."""
        output = " ".join(f"{count:{self.column_width}d}" for count in counts)
        if filename:
            output += f" {filename}"
        print(output, file=file, flush=True)

    def set_column_width(self, filenames):
        """
        Do the same as compute_number_width in GNU's wc.c
        """

        if not self.use_padding():
            self.column_width = 1
            return

        # If we don't actually have named files, we assume maximum width
        if not filenames:
            self.column_width = 1
            return
        else:
            # otherwise, we will start at 1 and work our way up
            self.column_width = 1

        total_size = 0

        # loop over files and check their sizes
        for name in filenames:
            if name is None:
                continue
            # hang on, this is stdin.
            if name == "-" or not name:
                self.column_width = 7
                break

            try:
                st = os.stat(name, follow_symlinks=False)
            except OSError:
                # Ignore errors. We don't want to complain about them early.
                # GNU does this because it's trying to preserve UNIX behaviour.
                continue

            if not stat.S_ISREG(st.st_mode):
                # yep, adding a dir to the list will cause GNU wc to use 7 as the column width.
                # Bug IMO, but we do the same.
                self.column_width = 7
                break
            else:
                # we have a regular file, and its size is the maximum size we will ever print.
                # because printing characters can't print a bigger number than that. This is, of course,
                # incorrect, because
                total_size += st.st_size
                new_width = len(str(total_size))
                self.column_width = max(self.column_width, new_width)
                if self.column_width >= 7:
                    # we have a file that is 7 digits long. We can stop now.
                    self.column_width = 7
                    break

    def use_padding(self):
        """
        GNU-specific padding rules.
        """
        # Check if we're using 'total=only'
        totals_only = hasattr(self.args, "total") and self.args.total == "only"
        columns = ("lines", "words", "bytes", "chars", "max_line_length")
        column_count = sum(1 for arg in columns if hasattr(self.args, arg) and getattr(self.args, arg))
        has_multiple_files = self.file_count > 1

        # GNU's totals-only row has no column padding.
        return not totals_only and (column_count > 1 or has_multiple_files)
