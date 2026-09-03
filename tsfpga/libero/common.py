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


def get_mss_configurator_path(mss_configurator_path: Path | None = None) -> Path:
    """
    Wrapper to get a path to the standalone Microcontroller Subsystem (MSS) Configurator
    executable. See :meth:`.LiberoTcl._add_mss_components` for more information.

    .. warning::
        The default executable name, ``"pfsoc_mss"``, has only been confirmed for the PolarFire
        SoC MSS Configurator, based on Microchip reference designs published on GitHub.
        Other device families that use an MSS (e.g. SmartFusion2) have their own MSS
        Configurator tool, with an executable name that has not been confirmed.
        For those, ``mss_configurator_path`` must be given explicitly.

    Arguments:
        mss_configurator_path: Path to the MSS Configurator executable.
            Leave as ``None`` to use whatever is available in the system ``PATH``
            (looking for an executable named ``"pfsoc_mss"``).
    """
    if mss_configurator_path is not None:
        return mss_configurator_path.resolve()

    which_mss_configurator = which("pfsoc_mss")
    if which_mss_configurator is None:
        raise FileNotFoundError(
            "Could not find 'pfsoc_mss' on PATH. "
            "Set 'mss_configurator_path' explicitly if using another MSS Configurator."
        )

    return Path(which_mss_configurator).resolve()


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
