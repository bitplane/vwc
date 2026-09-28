"""Fast reference cases for the counting core on the host.

The host may provide GNU or uutils wc; platform-specific formatting is
covered by the container integration suite instead.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

VWC = [sys.executable, "-m", "vwc.main"]
HOST_HAS_GNU_OPTIONS = b"--files0-from" in subprocess.run(["wc", "--help"], capture_output=True, check=False).stdout
HOST_IS_GNU = subprocess.run(["wc", "--version"], capture_output=True, check=False).stdout.startswith(
    b"wc (GNU coreutils)"
)


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"plain words\nsecond line\n",
        "wide: 界\tX\n".encode(),
        b"ab\rc\n",
        b"ab\fcd\n",
        b"\xc3\xa9\xff\n",
        b"one\0two\n",
    ],
)
@pytest.mark.parametrize("flag", ["-l", "-w", "-c", "-m", "-L"])
def test_host_counting(data, flag):
    if data == b"\xc3\xa9\xff\n" and flag == "-m" and not HOST_IS_GNU:
        pytest.skip("host wc uses different invalid-byte character counting")
    operands = [] if sys.platform.startswith(("darwin", "freebsd", "openbsd", "netbsd")) else ["-"]
    reference = subprocess.run(["wc", flag, *operands], input=data, capture_output=True, check=True)
    actual = subprocess.run([*VWC, flag, *operands], input=data, capture_output=True, check=True)
    assert actual.stdout == reference.stdout


@pytest.mark.skipif(not HOST_IS_GNU, reason="host wc is not GNU coreutils")
@pytest.mark.parametrize("locale_name", ["C", "C.UTF-8"])
def test_gnu_invalid_byte_word_count_follows_installed_version(locale_name):
    env = os.environ.copy()
    env["LC_ALL"] = locale_name
    data = b"\xff\n"
    reference = subprocess.run(["wc", "-w", "-"], input=data, capture_output=True, check=True, env=env)
    actual = subprocess.run([*VWC, "-w", "-"], input=data, capture_output=True, check=True, env=env)
    assert actual.stdout == reference.stdout


@pytest.mark.skipif(shutil.which("busybox") is None, reason="BusyBox is not installed")
@pytest.mark.parametrize("data", [b"", b"one two\n", b"ab\rc\n", "wide: 界\tX\n".encode()])
@pytest.mark.parametrize("flag", ["-l", "-c", "-m", "-L"])
def test_busybox_counting(tmp_path, data, flag):
    # Platform selection follows the first wc symlink on PATH.
    (tmp_path / "wc").symlink_to(shutil.which("busybox"))
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env['PATH']}"
    reference = subprocess.run(["busybox", "wc", flag, "-"], input=data, capture_output=True, check=True)
    actual = subprocess.run([*VWC, flag, "-"], input=data, capture_output=True, check=True, env=env)
    assert actual.stdout == reference.stdout


@pytest.mark.skipif(not HOST_HAS_GNU_OPTIONS, reason="host wc has no GNU options")
def test_files0_from_counts_and_totals(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.write_bytes(b"one\n")
    second.write_bytes(b"two\n")
    names = tmp_path / "names"
    names.write_bytes(os.fsencode(first) + b"\0" + os.fsencode(second) + b"\0")
    args = ["--files0-from", str(names)]
    reference = subprocess.run(["wc", *args], capture_output=True, check=True)
    actual = subprocess.run([*VWC, *args], capture_output=True, check=True)
    assert actual.stdout == reference.stdout


@pytest.mark.parametrize("names", [b"", b"{file}", b"{file}\0", b"\0", b"\0{file}\0", b"{file}\0\0"])
@pytest.mark.skipif(not HOST_HAS_GNU_OPTIONS, reason="host wc has no GNU options")
def test_files0_from_edge_cases(tmp_path, names):
    item = tmp_path / "item"
    item.write_bytes(b"one\n")
    source = tmp_path / "names"
    source.write_bytes(names.replace(b"{file}", os.fsencode(item)))
    reference = subprocess.run(["wc", "--files0-from", str(source)], capture_output=True, check=False)
    actual = subprocess.run([*VWC, "--files0-from", str(source)], capture_output=True, check=False)
    assert (actual.returncode, actual.stdout) == (reference.returncode, reference.stdout)
    assert actual.stderr.replace(b"main.py:", b"wc:") == reference.stderr


@pytest.mark.skipif(not HOST_IS_GNU, reason="GNU stdin error wording requires GNU wc")
def test_files0_from_stdin_rejects_stdin_filename():
    reference = subprocess.run(["wc", "--files0-from=-"], input=b"-\0", capture_output=True, check=False)
    actual = subprocess.run([*VWC, "--files0-from=-"], input=b"-\0", capture_output=True, check=False)
    assert (actual.returncode, actual.stdout) == (reference.returncode, reference.stdout)
    assert actual.stderr.replace(b"main.py:", b"wc:") == reference.stderr


@pytest.mark.parametrize("kind", ["missing_source", "extra_operand", "missing_input"])
def test_host_errors(tmp_path, kind):
    if kind != "missing_input" and not HOST_HAS_GNU_OPTIONS:
        pytest.skip("host wc has no GNU options")
    existing = tmp_path / "existing"
    existing.write_bytes(b"one\n")
    missing = tmp_path / "missing"
    if kind == "missing_source":
        args = ["--files0-from", str(missing)]
    elif kind == "extra_operand":
        source = tmp_path / "names"
        source.write_bytes(os.fsencode(existing) + b"\0")
        args = ["--files0-from", str(source), str(existing)]
    else:
        args = [str(existing), str(missing), str(existing)]

    # Invoke both programs as wc so their error prefixes match.
    wrapper = tmp_path / "wc"
    wrapper.symlink_to(Path(sys.executable).parent / "vwc")
    reference = subprocess.run(["wc", *args], capture_output=True, check=False)
    actual = subprocess.run([str(wrapper), *args], capture_output=True, check=False)
    assert (actual.returncode, actual.stdout, actual.stderr) == (
        reference.returncode,
        reference.stdout,
        reference.stderr,
    )


@pytest.mark.skipif(not HOST_HAS_GNU_OPTIONS, reason="host wc has no GNU options")
def test_version_does_not_read_stdin():
    actual = subprocess.run([*VWC, "--version"], input=b"ignored", capture_output=True, check=True)
    assert actual.stdout.startswith(b"vwc ")


@pytest.mark.skipif(not HOST_HAS_GNU_OPTIONS, reason="host wc has no GNU options")
def test_total_only_has_no_padding(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.write_bytes(b"one\n")
    second.write_bytes(b"two words\n")
    args = ["--total=only", str(first), str(second)]
    reference = subprocess.run(["wc", *args], capture_output=True, check=True)
    actual = subprocess.run([*VWC, *args], capture_output=True, check=True)
    assert actual.stdout == reference.stdout


@pytest.mark.parametrize("option", ["-z", "--nonsense"])
def test_invalid_option_uses_native_error_status(option):
    reference = subprocess.run(["wc", option], capture_output=True, check=False)
    actual = subprocess.run([*VWC, option], capture_output=True, check=False)
    assert actual.returncode == reference.returncode == 1


@pytest.mark.skipif(shutil.which("busybox") is None, reason="BusyBox is not installed")
def test_busybox_invalid_option_status(tmp_path):
    (tmp_path / "wc").symlink_to(shutil.which("busybox"))
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env['PATH']}"
    actual = subprocess.run([*VWC, "-z"], capture_output=True, check=False, env=env)
    assert actual.returncode == 1


@pytest.mark.parametrize(
    "script", sorted((Path(__file__).parent / "integration" / "test_scripts").glob("*.sh")), ids=lambda p: p.stem
)
@pytest.mark.parametrize("reference", ["wc", "busybox"])
def test_existing_scripts_locally(tmp_path, script, reference):
    if reference == "busybox" and shutil.which("busybox") is None:
        pytest.skip("BusyBox is not installed")
    if script.stem in {"gnu_options", "gnu_encoding"} and reference == "wc" and not HOST_IS_GNU:
        pytest.skip("GNU reference script requires GNU wc")

    native_bin = tmp_path / "native_bin"
    vwc_bin = tmp_path / "vwc_bin"
    native_bin.mkdir()
    vwc_bin.mkdir()
    native_bin.joinpath("wc").symlink_to(shutil.which(reference))
    vwc_bin.joinpath("wc").symlink_to(Path(sys.executable).parent / "vwc")

    outputs = []
    for name, prefix in (("native", native_bin), ("vwc", vwc_bin)):
        work = tmp_path / name
        work.mkdir()
        env = os.environ.copy()
        env["PATH"] = f"{prefix}{os.pathsep}{native_bin}{os.pathsep}{env['PATH']}"
        result = subprocess.run(["/bin/sh", str(script)], cwd=work, env=env, capture_output=True, check=False)
        outputs.append((result.returncode, result.stdout, result.stderr))
    assert outputs[1] == outputs[0]
