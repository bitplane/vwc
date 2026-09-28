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

    def accelerated_word_mode(self):
        if codecs.lookup(self.encoding).name in ("ascii", "utf-8"):
            return "unicode"
        return None

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


class NetBSD(BSD):
    """NetBSD wc reports malformed multibyte input and prints failed reads."""

    def process_file(self, filename, file_obj):
        self.current_filename = filename or "<stdin>"
        WC.process_file(self, filename, file_obj)

    def accelerated_word_mode(self):
        return None

    def process_line(self, line):
        if (self.args.words or self.args.chars or self.args.max_line_length) and codecs.lookup(
            self.encoding
        ).name != "ascii":
            decoded = line.decode(self.encoding, errors="surrogateescape")
            invalid = sum(0xDC80 <= ord(char) <= 0xDCFF for char in decoded)
            if invalid:
                exe = os.path.basename(sys.argv[0])
                filename = getattr(self, "current_filename", "")
                try:
                    line.decode(self.encoding)
                except UnicodeDecodeError as error:
                    incomplete = error.reason == "unexpected end of data" and not line.endswith(b"\n")
                    if incomplete:
                        if self.args.chars:
                            sys.stderr.write(f"{exe}: {filename}: incomplete multibyte character\n")
                            self.set_status(1)
                    else:
                        for _ in range(invalid):
                            sys.stderr.write(f"{exe}: {filename}: invalid byte sequence\n")
                        self.set_status(1)
        WC.process_line(self, line)

    def count_chars(self, line, text):
        if codecs.lookup(self.encoding).name == "ascii":
            return len(line)
        return sum(not 0xDC80 <= ord(char) <= 0xDCFF for char in text)

    def count_words(self, line, text):
        if codecs.lookup(self.encoding).name == "ascii":
            return len(line.split())
        return len("".join(char for char in text if not 0xDC80 <= ord(char) <= 0xDCFF).split())

    def line_width(self, line, text):
        if not line.endswith(b"\n"):
            return 0
        if codecs.lookup(self.encoding).name == "ascii":
            return len(line.removesuffix(b"\n"))
        return sum(not 0xDC80 <= ord(char) <= 0xDCFF for char in text.removesuffix("\n"))

    def handle_error(self, error, filename):
        if isinstance(error, IsADirectoryError):
            self.reset_counts()
            if self.args.bytes and not (
                self.args.lines or self.args.words or self.args.chars or self.args.max_line_length
            ):
                self.bytes = os.stat(filename).st_size
                self.print_counts(filename)
                self.update_totals()
                return
            self.handle_read_error(error, filename)
            return
        exe = os.path.basename(sys.argv[0])
        sys.stderr.write(f"{exe}: {filename}: {error.strerror}\n")
        self.set_status(1)

    def handle_read_error(self, error, filename):
        exe = os.path.basename(sys.argv[0])
        sys.stderr.write(f"{exe}: {filename}: {error.strerror}\n")
        self.set_status(1)
        self.print_counts(filename)
        self.update_totals()


class OpenBSD(BSD):
    """OpenBSD wc uses byte words unless -m and supports -h instead of -L."""

    def add_platform_args(self, parser):
        parser.add_argument("-h", action="store_true", dest="human", help="print human-readable counts")

    def parse_args(self, argv):
        for token in argv:
            if token == "--":
                break
            if token.startswith("-") and token != "-":
                for option in token[1:]:
                    if option not in "clwmh":
                        exe = os.path.basename(sys.argv[0])
                        sys.stderr.write(f"{exe}: unknown option -- {option}\n")
                        sys.stderr.write("usage: wc [-c | -m] [-hlw] [file ...]\n")
                        raise SystemExit(1)
        WC.parse_args(self, argv)
        self.multibyte = any("m" in token[1:] for token in argv if token.startswith("-") and token != "-")
        if self.args.bytes or self.args.chars:
            self.args.chars = True
            self.args.bytes = False

    def process_line(self, line):
        WC.process_line(self, line)

    def count_words(self, line, text):
        if self.multibyte and codecs.lookup(self.encoding).name != "ascii":
            return len(text.split())
        return len(line.split())

    def accelerated_word_mode(self):
        if not self.multibyte:
            return "openbsd"
        return None

    def count_chars(self, line, text):
        if self.multibyte and codecs.lookup(self.encoding).name != "ascii":
            return len(text)
        return len(line)

    @staticmethod
    def format_scaled(count):
        # OpenBSD's fmt_scaled(3) uses one decimal below 100 units, then
        # rounds to an integer. All wc counts are nonnegative.
        suffixes = "BKMGTPE"
        unit = 0
        while count >= 1024 ** (unit + 1) and unit < len(suffixes) - 1:
            unit += 1
        scale = 1024**unit
        whole = count // scale
        fraction = 0 if unit == 0 else ((count % scale) // (scale // 1024) * 10 + 512) // 1024
        if fraction >= 10:
            whole += 1
            fraction = 0
        if whole == 0:
            return "0B"
        if unit == 0 or whole >= 100:
            if fraction >= 5:
                whole += 1
            return f"{whole}{suffixes[unit]}"
        return f"{whole}.{fraction}{suffixes[unit]}"

    def print_line(self, counts, filename, file=sys.stdout):
        if self.args.human:
            output = "".join(f"{self.format_scaled(count):>7}" for count in counts)
            if filename:
                output += f" {filename}"
            print(output, file=file, flush=True)
            return
        super().print_line(counts, filename, file)

    def handle_error(self, error, filename):
        if isinstance(error, IsADirectoryError):
            self.reset_counts()
            if self.args.chars and not (self.args.lines or self.args.words) and not self.multibyte:
                self.chars = os.stat(filename).st_size
                self.print_counts(filename)
                self.update_totals()
                return
            self.handle_read_error(error, filename)
            return
        exe = os.path.basename(sys.argv[0])
        sys.stderr.write(f"{exe}: {filename}: {error.strerror}\n")
        self.set_status(1)

    def handle_read_error(self, error, filename):
        exe = os.path.basename(sys.argv[0])
        sys.stderr.write(f"{exe}: {filename or '(stdin)'}: {error.strerror}\n")
        self.set_status(1)
        self.print_counts(filename)
        self.update_totals()
