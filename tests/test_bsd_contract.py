"""BSD behavior documented by Apple's text_cmds/wc/wc.c.

The macOS CI job compares the full CLI with the native wc implementation.
"""

import io

import pytest

from vwc.wc.bsd import BSD


@pytest.mark.parametrize(
    ("options", "bytes_enabled", "chars_enabled"),
    [(["-cm"], False, True), (["-mc"], True, False), (["-m", "-c"], True, False)],
)
def test_last_character_option_wins(options, bytes_enabled, chars_enabled):
    wc = BSD()
    wc.parse_args(options)
    assert (wc.args.bytes, wc.args.chars) == (bytes_enabled, chars_enabled)


def test_invalid_bsd_option_exits_one():
    with pytest.raises(SystemExit) as result:
        BSD().parse_args(["-z"])
    assert result.value.code == 1


@pytest.mark.parametrize(
    ("options", "expected"),
    [(["-L"], 5), (["-mL"], 3), (["-mcL"], 5)],
)
def test_longest_line_counts_bytes_unless_multibyte(options, expected):
    wc = BSD()
    wc.parse_args(options)
    wc.encoding = "utf-8"
    wc.process_line("界\tX\n".encode())
    assert wc.max_width == expected


def test_count_output_has_leading_fields_and_no_trailing_space():
    wc = BSD()
    output = io.StringIO()
    wc.print_line([1, 2], "name", output)
    wc.print_line([1], "", output)
    assert output.getvalue() == "       1       2 name\n       1\n"


def test_unterminated_final_line_does_not_extend_bsd_longest_line():
    wc = BSD()
    wc.parse_args(["-L"])
    wc.encoding = "utf-8"
    wc.process_line(b"ab\n")
    wc.process_line(b"long final line")
    assert wc.max_width == 2


def test_invalid_multibyte_input_warns_once_for_bsd_m(capsys):
    wc = BSD()
    wc.parse_args(["-m"])
    wc.encoding = "utf-8"
    wc.process_line(b"\xff\n")
    wc.process_line(b"\xfe\n")
    assert wc.chars == 4
    assert capsys.readouterr().err.count("stdin:") == 1


def test_incomplete_final_multibyte_sequence_is_not_a_character(capsys):
    wc = BSD()
    wc.parse_args(["-m"])
    wc.encoding = "utf-8"
    wc.process_line(b"a\xc3")
    assert wc.chars == 1
    assert "stdin:" in capsys.readouterr().err


def test_named_dash_is_a_file(tmp_path, monkeypatch):
    (tmp_path / "-").write_bytes(b"named file\n")
    monkeypatch.chdir(tmp_path)
    with BSD().open_file("-") as source:
        assert source.read() == b"named file\n"


def test_bsd_directory_is_a_read_error(tmp_path, capsys):
    directory = tmp_path / "directory"
    directory.mkdir()
    wc = BSD()
    wc.parse_args([str(directory)])
    assert wc.run() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"{directory}: read: Is a directory" in captured.err
