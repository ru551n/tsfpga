# --------------------------------------------------------------------------------------------------
# Copyright (c) Lukas Vik. All rights reserved.
#
# This file is part of the tsfpga project, a project platform for modern FPGA development.
# https://tsfpga.com
# https://github.com/tsfpga/tsfpga
# --------------------------------------------------------------------------------------------------

from __future__ import annotations

import os
from pathlib import Path
from shutil import which

from vunit.ostools import Process


def run_ghdl(ghdl_path: Path | None, arguments: list[str], cwd: Path) -> bool:
    """
    Run GHDL with the given arguments.
    Used for analyzing VHDL source files into an on-disk library, which can later be picked up
    by the ``ghdl-yosys-plugin`` when running :func:`run_yosys`.

    Setting ``cwd`` ensures that any files produced (e.g. GHDL library files) end up in a
    well-known location.

    Arguments:
        ghdl_path: Path to the GHDL executable. Can be set to ``None``
            to use whatever version is in ``PATH``.
        arguments: Arguments that shall be passed on to GHDL.
        cwd: The GHDL process will be executed with this as the working directory.

    Return:
        True if everything went well.
    """
    cmd = [str(get_ghdl_path(ghdl_path)), *arguments]

    try:
        Process(args=cmd, cwd=cwd).consume_output()
    except Process.NonZeroExitCode:
        return False
    return True


def run_yosys(
    yosys_path: Path | None,
    ghdl_plugin_path: Path | None,
    script_file: Path,
    cwd: Path,
    ghdl_prefix: Path | None = None,
) -> bool:
    """
    Run Yosys with the given script.

    Setting ``cwd`` ensures that any files produced (e.g. reports, netlists) end up in a
    well-known location.

    Arguments:
        yosys_path: Path to the Yosys executable. Can be set to ``None``
            to use whatever version is in ``PATH``.
        ghdl_plugin_path: Path to the ``ghdl-yosys-plugin`` module (typically named ``ghdl.so``).
            Can be set to ``None`` if the plugin is already available to Yosys without explicitly
            loading it (e.g. if it has been installed in the Yosys plugin directory).
        script_file: Path to a file containing the Yosys commands that shall be executed.
        cwd: The Yosys process will be executed with this as the working directory.
        ghdl_prefix: Value to set the ``GHDL_PREFIX`` environment variable to for this process.
            The ``ghdl-yosys-plugin`` module is a separate binary from the ``ghdl`` executable,
            and does not necessarily know where to find the GHDL standard libraries
            (``std``, ``ieee``, ...) on its own.
            Corresponds to the "library prefix" printed by ``ghdl --disp-config``.
            Can be left out if the plugin already finds the libraries on its own (e.g. if GHDL
            was installed in a standard system location), or if ``GHDL_PREFIX`` is already set
            in the calling environment.

    Return:
        True if everything went well.
    """
    cmd = [str(get_yosys_path(yosys_path))]

    if ghdl_plugin_path is not None:
        cmd += ["-m", str(ghdl_plugin_path.resolve())]

    cmd += ["-s", str(script_file.resolve())]

    env = None
    if ghdl_prefix is not None:
        env = dict(os.environ)
        env["GHDL_PREFIX"] = str(ghdl_prefix.resolve())

    try:
        Process(args=cmd, cwd=cwd, env=env).consume_output()
    except Process.NonZeroExitCode:
        return False
    return True


def get_ghdl_path(ghdl_path: Path | None = None) -> Path:
    """
    Wrapper to get a path to the GHDL executable.

    Arguments:
        ghdl_path: Path to the GHDL executable.
            Leave as ``None`` to use whatever is available in the system ``PATH``.
    """
    if ghdl_path is not None:
        return ghdl_path.resolve()

    which_ghdl = which("ghdl")
    if which_ghdl is None:
        raise FileNotFoundError("Could not find ghdl on PATH")

    return Path(which_ghdl).resolve()


def to_yosys_path(path: Path) -> str:
    """
    Return a path string in a format suitable to embed in a Yosys command script.
    """
    return str(path.resolve()).replace("\\", "/")


def get_yosys_path(yosys_path: Path | None = None) -> Path:
    """
    Wrapper to get a path to the Yosys executable.

    Arguments:
        yosys_path: Path to the Yosys executable.
            Leave as ``None`` to use whatever is available in the system ``PATH``.
    """
    if yosys_path is not None:
        return yosys_path.resolve()

    which_yosys = which("yosys")
    if which_yosys is None:
        raise FileNotFoundError("Could not find yosys on PATH")

    return Path(which_yosys).resolve()
