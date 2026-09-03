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

from tsfpga.libero.common import (
    get_libero_path,
    get_libero_version,
    get_mss_configurator_path,
    run_libero_gui,
    run_libero_tcl,
)

THIS_DIR = Path(__file__).parent


def test_run_libero_tcl():
    libero_path = THIS_DIR / "libero.exe"
    tcl_file = THIS_DIR / "script.tcl"
    expected_cmd = [
        str(libero_path.resolve()),
        f"script:{tcl_file.resolve()}",
        f"logfile:{tcl_file.resolve().with_suffix('.log')}",
    ]

    with patch("tsfpga.libero.common.Process") as mocked_process:
        mocked_process.NonZeroExitCode = ValueError
        assert run_libero_tcl(libero_path, tcl_file)
        mocked_process.assert_called_once_with(args=expected_cmd, cwd=THIS_DIR)

    with patch("tsfpga.libero.common.Process") as mocked_process:
        mocked_process.NonZeroExitCode = ValueError
        mocked_process.return_value.consume_output.side_effect = ValueError("Non-zero exit code!")
        assert not run_libero_tcl(libero_path, tcl_file)


def test_run_libero_gui(tmp_path):
    libero_path = THIS_DIR / "libero.exe"
    project_file = tmp_path / "name.prjx"
    project_file.write_text("")

    expected_cmd = [str(libero_path.resolve()), str(project_file.resolve())]

    with patch("tsfpga.libero.common.Process") as mocked_process:
        mocked_process.NonZeroExitCode = ValueError
        assert run_libero_gui(libero_path, project_file)
        mocked_process.assert_called_once_with(args=expected_cmd, cwd=tmp_path)


def test_run_libero_gui_should_raise_exception_if_project_does_not_exist(tmp_path):
    project_file = tmp_path / "name.prjx"
    with pytest.raises(FileNotFoundError) as exception_info:
        run_libero_gui(THIS_DIR / "libero.exe", project_file)
    assert str(exception_info.value) == f"Project does not exist: {project_file.resolve()}"


def test_get_libero_path_with_explicit_path():
    libero_path = THIS_DIR / "libero.exe"
    assert get_libero_path(libero_path) == libero_path.resolve()


def test_get_libero_path_should_raise_exception_if_not_found_on_path():
    with patch("tsfpga.libero.common.which", return_value=None) as _:
        with pytest.raises(FileNotFoundError) as exception_info:
            get_libero_path(None)
        assert str(exception_info.value) == "Could not find libero on PATH"


def test_get_libero_version():
    libero_path = Path("/opt/Microchip/Libero_SoC_v2023.1/bin64/libero")
    assert get_libero_version(libero_path=libero_path) == "Libero_SoC_v2023.1"


def test_get_mss_configurator_path_with_explicit_path():
    mss_configurator_path = THIS_DIR / "pfsoc_mss.exe"
    assert get_mss_configurator_path(mss_configurator_path) == mss_configurator_path.resolve()


def test_get_mss_configurator_path_should_raise_exception_if_not_found_on_path():
    with patch("tsfpga.libero.common.which", return_value=None) as _:
        with pytest.raises(FileNotFoundError) as exception_info:
            get_mss_configurator_path(None)
        assert str(exception_info.value) == (
            "Could not find 'pfsoc_mss' on PATH. "
            "Set 'mss_configurator_path' explicitly if using another MSS Configurator."
        )
