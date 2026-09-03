# --------------------------------------------------------------------------------------------------
# Copyright (c) Lukas Vik. All rights reserved.
#
# This file is part of the tsfpga project, a project platform for modern FPGA development.
# https://tsfpga.com
# https://github.com/tsfpga/tsfpga
# --------------------------------------------------------------------------------------------------

from pathlib import Path
from unittest.mock import patch

import pytest

from tsfpga.yosys.common import get_ghdl_path, get_yosys_path, run_ghdl, run_yosys, to_yosys_path

THIS_DIR = Path(__file__).parent


def test_run_ghdl():
    ghdl_path = THIS_DIR / "ghdl.exe"
    arguments = ["-a", "--std=08", "apa.vhd"]
    expected_cmd = [str(ghdl_path.resolve()), *arguments]

    with patch("tsfpga.yosys.common.Process") as mocked_process:
        mocked_process.NonZeroExitCode = ValueError
        assert run_ghdl(ghdl_path=ghdl_path, arguments=arguments, cwd=THIS_DIR)
        mocked_process.assert_called_once_with(args=expected_cmd, cwd=THIS_DIR)

    with patch("tsfpga.yosys.common.Process") as mocked_process:
        mocked_process.NonZeroExitCode = ValueError
        mocked_process.return_value.consume_output.side_effect = ValueError("Non-zero exit code!")
        assert not run_ghdl(ghdl_path=ghdl_path, arguments=arguments, cwd=THIS_DIR)


def test_run_yosys():
    yosys_path = THIS_DIR / "yosys.exe"
    ghdl_plugin_path = THIS_DIR / "ghdl.so"
    script_file = THIS_DIR / "apa.ys"
    expected_cmd = [
        str(yosys_path.resolve()),
        "-m",
        str(ghdl_plugin_path.resolve()),
        "-s",
        str(script_file.resolve()),
    ]

    with patch("tsfpga.yosys.common.Process") as mocked_process:
        mocked_process.NonZeroExitCode = ValueError
        assert run_yosys(
            yosys_path=yosys_path,
            ghdl_plugin_path=ghdl_plugin_path,
            script_file=script_file,
            cwd=THIS_DIR,
        )
        mocked_process.assert_called_once_with(args=expected_cmd, cwd=THIS_DIR, env=None)

    with patch("tsfpga.yosys.common.Process") as mocked_process:
        mocked_process.NonZeroExitCode = ValueError
        mocked_process.return_value.consume_output.side_effect = ValueError("Non-zero exit code!")
        assert not run_yosys(
            yosys_path=yosys_path,
            ghdl_plugin_path=None,
            script_file=script_file,
            cwd=THIS_DIR,
        )


def test_run_yosys_without_plugin_does_not_add_dash_m_argument():
    yosys_path = THIS_DIR / "yosys.exe"
    script_file = THIS_DIR / "apa.ys"
    expected_cmd = [str(yosys_path.resolve()), "-s", str(script_file.resolve())]

    with patch("tsfpga.yosys.common.Process") as mocked_process:
        mocked_process.NonZeroExitCode = ValueError
        assert run_yosys(
            yosys_path=yosys_path, ghdl_plugin_path=None, script_file=script_file, cwd=THIS_DIR
        )
        mocked_process.assert_called_once_with(args=expected_cmd, cwd=THIS_DIR, env=None)


def test_run_yosys_sets_ghdl_prefix_environment_variable():
    yosys_path = THIS_DIR / "yosys.exe"
    script_file = THIS_DIR / "apa.ys"
    ghdl_prefix = THIS_DIR / "ghdl_libs"

    with patch("tsfpga.yosys.common.Process") as mocked_process:
        mocked_process.NonZeroExitCode = ValueError
        assert run_yosys(
            yosys_path=yosys_path,
            ghdl_plugin_path=None,
            script_file=script_file,
            cwd=THIS_DIR,
            ghdl_prefix=ghdl_prefix,
        )
        _, kwargs = mocked_process.call_args
        assert kwargs["env"]["GHDL_PREFIX"] == str(ghdl_prefix.resolve())


def test_get_ghdl_path_raises_exception_if_not_found_in_path():
    with (
        patch("tsfpga.yosys.common.which", return_value=None),
        pytest.raises(FileNotFoundError, match="Could not find ghdl on PATH"),
    ):
        get_ghdl_path()


def test_get_yosys_path_raises_exception_if_not_found_in_path():
    with (
        patch("tsfpga.yosys.common.which", return_value=None),
        pytest.raises(FileNotFoundError, match="Could not find yosys on PATH"),
    ):
        get_yosys_path()


def test_get_ghdl_path_with_explicit_path_does_not_check_path_env_variable():
    ghdl_path = THIS_DIR / "ghdl.exe"
    with patch("tsfpga.yosys.common.which") as mocked_which:
        assert get_ghdl_path(ghdl_path) == ghdl_path.resolve()
        mocked_which.assert_not_called()


def test_to_yosys_path():
    assert to_yosys_path(THIS_DIR / "apa.vhd") == str((THIS_DIR / "apa.vhd").resolve())
