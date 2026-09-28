"""Large-stream cases that exercise the optional Numba scanner."""

import os
import select
import subprocess
import sys
import time

import pytest

pytest.importorskip("numba")


@pytest.mark.parametrize("mode", ["gnu_c", "gnu_legacy_c", "busybox", "openbsd", "unicode_ascii"])
def test_scanner_preserves_word_state_across_chunks(mode):
    from vwc.wc import accelerated

    data = b"first\xff\xa0second\x1cthird\nlast"
    if mode == "unicode_ascii":
        data = data.replace(b"\xff\xa0", b" ")
    number = {
        "gnu_c": accelerated.GNU_C,
        "gnu_legacy_c": accelerated.GNU_LEGACY_C,
        "busybox": accelerated.BUSYBOX,
        "openbsd": accelerated.OPENBSD,
        "unicode_ascii": accelerated.UNICODE_ASCII,
    }[mode]
    whole = accelerated.scan(data, False, number, True)
    first = accelerated.scan(data[:7], False, number, True)
    second = accelerated.scan(data[7:13], first[2], number, True)
    third = accelerated.scan(data[13:], second[2], number, True)
    assert (first[0] + second[0] + third[0], first[1] + second[1] + third[1], third[2]) == whole
    if mode != "unicode_ascii":
        from vwc.wc.wc import WC

        small = WC.count_byte_words(data[:7], False, mode)
        large = accelerated.scan(data[7:], small[1], number, True)
        assert (small[0] + large[1], large[2]) == whole[1:]


@pytest.mark.parametrize("locale_name", ["C", "C.UTF-8"])
@pytest.mark.parametrize("flag", ["-l", "-w", "-c", "-lwc"])
def test_large_regular_file_matches_native_wc(tmp_path, locale_name, flag):
    data = (b"word\xc2\xa0more next\n" * 240_000) + b"tail"
    path = tmp_path / "large"
    path.write_bytes(data)
    env = os.environ.copy()
    env["LC_ALL"] = locale_name
    expected = subprocess.run(["wc", flag, str(path)], capture_output=True, check=True, env=env)
    actual = subprocess.run(
        [sys.executable, "-m", "vwc.main", flag, str(path)], capture_output=True, check=True, env=env
    )
    assert actual.stdout == expected.stdout


def test_stream_without_newlines_matches_native_wc():
    # A long, open line must be scanned in chunks rather than held until EOF.
    data = b"a " * (1024 * 1024) + b"\xc3\xa9" + b" b" * (1024 * 1024)
    expected = subprocess.run(["wc", "-lwc"], input=data, capture_output=True, check=True)
    actual = subprocess.run([sys.executable, "-m", "vwc.main", "-lwc"], input=data, capture_output=True, check=True)
    assert actual.stdout == expected.stdout


def test_open_stream_shows_progress_before_eof():
    master, slave = os.openpty()
    process = subprocess.Popen(
        [sys.executable, "-m", "vwc.main"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=slave
    )
    os.close(slave)
    progress = b""
    try:
        for _ in range(20):
            process.stdin.write(b"longword " * 8192)
            process.stdin.flush()
            time.sleep(0.08)
            if select.select([master], [], [], 0)[0]:
                progress += os.read(master, 65536)
                break
        assert progress, "no live count appeared while stdin remained open"
    finally:
        process.stdin.close()
        process.wait(timeout=5)
        os.close(master)
