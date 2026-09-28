# src/vwc/wc/bsd.py
import codecs
import errno
import os
import sys

from .wc import WC


class BSD(WC):
    """
    wc - count lines, words, characters, and bytes

    Usage: wc [-clmwL] [file ...]

    Count lines, words, characters, and bytes for each input file.
    With no file, or when file is -, read standard input.
    """

    def add_platform_args(self, parser):
        """BSD-specific arguments."""
        # BSD supports -L but without long option
        parser.add_argument(
            "-L", action="store_true", dest="max_line_length", help="print the length of the longest line in bytes"
        )

    def parse_args(self, argv):
        super().parse_args(argv)
        # BSD wc has one character-count column. The last -c or -m wins,
        # including when the options appear in a combined short-option group.
        last_count_option = None
        for token in argv:
            if token == "--":
                break
            if token.startswith("-") and token != "-":
                for option in token[1:]:
                    if option in "cm":
                        last_count_option = option
        if last_count_option == "c":
            self.args.bytes, self.args.chars = True, False
        elif last_count_option == "m":
            self.args.bytes, self.args.chars = False, True

    def open_file(self, filename):
        return sys.stdin.buffer if not filename else open(filename, "rb")

    def line_width(self, line, text):
        # BSD wc only commits the longest-line count at a newline.
        if not line.endswith(b"\n"):
            return 0
        if self.args.chars and codecs.lookup(self.encoding).name != "ascii":
            return len(text.removesuffix("\n"))
        return len(line.removesuffix(b"\n"))

    def count_chars(self, line, text):
        if codecs.lookup(self.encoding).name == "ascii":
            return len(line)
        decoder = codecs.getincrementaldecoder(self.encoding)(errors="surrogateescape")
        # BSD's mbrtowc loop leaves an incomplete sequence at EOF uncounted.
        return len(decoder.decode(line, final=False))

    def handle_error(self, error, filename):
        if isinstance(error, IsADirectoryError):
            # Python rejects the directory during open; BSD open succeeds and
            # reports the directory when it is read.
            self.handle_read_error(error, filename)
            return
        exe = sys.argv[0].rsplit("/", 1)[-1]
        sys.stderr.write(f"{exe}: {filename}: open: {error.strerror}\n")
        self.set_status(1)

    def handle_read_error(self, error, filename):
        exe = sys.argv[0].rsplit("/", 1)[-1]
        sys.stderr.write(f"{exe}: {filename}: read: {error.strerror}\n")
        self.set_status(1)

    def process_file(self, filename, file_obj):
        self.current_filename = filename or "stdin"
        self.warned_invalid = False
        super().process_file(filename, file_obj)

    def process_line(self, line):
        if (
            self.args.chars
            and codecs.lookup(self.encoding).name != "ascii"
            and not getattr(self, "warned_invalid", False)
        ):
            try:
                line.decode(self.encoding)
            except UnicodeDecodeError:
                exe = os.path.basename(sys.argv[0])
                filename = getattr(self, "current_filename", "stdin")
                sys.stderr.write(f"{exe}: {filename}: {os.strerror(errno.EILSEQ)}\n")
                self.warned_invalid = True
        super().process_line(line)

    def print_line(self, counts, filename, file=sys.stdout):
        """Format and print count line for a file with BSD formatting."""
        # BSD format: 7-character fields right-justified
        output = "".join(f" {count:7d}" for count in counts)

        # Add filename if not empty
        if filename:
            output += f" {filename}"

        print(output, file=file, flush=True)
