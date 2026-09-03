# --------------------------------------------------------------------------------------------------
# Copyright (c) Lukas Vik. All rights reserved.
#
# This file is part of the tsfpga project, a project platform for modern FPGA development.
# https://tsfpga.com
# https://github.com/tsfpga/tsfpga
# --------------------------------------------------------------------------------------------------

from __future__ import annotations

from pathlib import Path
from shutil import which

from vunit.ostools import Process


def run_libero_tcl(libero_path: Path | None, tcl_file: Path) -> bool:
    """
    Setting cwd ensures that any log files produced are placed in
    the same directory as the TCL file that produced them.

    Arguments:
        libero_path: Path to Libero SoC executable. Can set to ``None``
            to use whatever version is in ``PATH``.
        tcl_file: Path to TCL file.

    Return:
        True if everything went well.
    """
    tcl_file = tcl_file.resolve()
    log_file = tcl_file.with_suffix(".log")

    cmd = [
        str(get_libero_path(libero_path)),
        f"script:{tcl_file}",
        f"logfile:{log_file}",
    ]

    try:
        Process(args=cmd, cwd=tcl_file.parent).consume_output()
    except Process.NonZeroExitCode:
        return False
    return True


def run_libero_gui(libero_path: Path | None, project_file: Path) -> bool:
    """
    Setting cwd ensures that any log files produced are placed in
    the same directory as the project.

    Arguments:
        libero_path: Path to Libero SoC executable.
            Leave as ``None`` to use whatever is available in the system ``PATH``.
        project_file: Path to a project .prjx file.

    Return:
        True if everything went well.
    """
    project_file = project_file.resolve()
    if not project_file.exists():
        raise FileNotFoundError(f"Project does not exist: {project_file}")

    cmd = [str(get_libero_path(libero_path)), str(project_file)]

    try:
        Process(args=cmd, cwd=project_file.parent).consume_output()
    except Process.NonZeroExitCode:
        return False
    return True


def get_libero_path(libero_path: Path | None = None) -> Path:
    """
    Wrapper to get a path to the Libero SoC executable.

    Arguments:
        libero_path: Path to Libero SoC executable.
            Leave as ``None`` to use whatever is available in the system ``PATH``.
    """
    if libero_path is not None:
        return libero_path.resolve()

    which_libero = which("libero")
    if which_libero is None:
        raise FileNotFoundError("Could not find libero on PATH")

    return Path(which_libero).resolve()


def get_libero_version(libero_path: Path | None = None) -> str:
    """
    Get the version number of the Libero SoC installation.

    .. note::
        This is a best-effort implementation based on the conventional Libero SoC installation
        directory structure (e.g. ``.../Microchip/Libero_SoC_v2023.1/bin64/libero``).
        It has not been verified against a real installation.
        Consider it a placeholder that might need adjustment.

    Arguments:
        libero_path: Path to Libero SoC executable.
            Leave as ``None`` to use whatever is available in the system ``PATH``.

    Return:
        The version, e.g. ``"Libero_SoC_v2023.1"``.
    """
    libero_path = get_libero_path(libero_path=libero_path)

    # E.g. ".../Microchip/Libero_SoC_v2023.1/bin64/libero" -> "Libero_SoC_v2023.1"
    return libero_path.parent.parent.name
