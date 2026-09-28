"""Optional chunk scanner for the byte-oriented counting paths."""

import numpy as np
from numba import njit

UNICODE_ASCII = 0
GNU_C = 1
GNU_LEGACY_C = 2
BUSYBOX = 3
OPENBSD = 4


@njit(cache=True)
def _scan(data, in_word, mode, count_words):
    lines = 0
    words = 0
    for byte in data:
        if byte == 10:
            lines += 1
        if not count_words:
            continue

        ascii_space = byte == 9 or byte == 10 or byte == 11 or byte == 12 or byte == 13 or byte == 32
        if mode == BUSYBOX:
            if ascii_space:
                in_word = False
            elif 33 <= byte <= 126 and not in_word:
                words += 1
                in_word = True
        elif mode == GNU_LEGACY_C:
            if byte >= 128:
                continue
            if ascii_space or 28 <= byte <= 31:
                in_word = False
            elif not in_word:
                words += 1
                in_word = True
        else:
            is_space = ascii_space
            if mode == UNICODE_ASCII:
                is_space = is_space or 28 <= byte <= 31
            elif mode == GNU_C:
                is_space = is_space or byte == 160
            if is_space:
                in_word = False
            elif not in_word:
                words += 1
                in_word = True
    return lines, words, in_word


def scan(data, in_word, mode, count_words):
    return _scan(np.frombuffer(data, dtype=np.uint8), in_word, mode, count_words)
