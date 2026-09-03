# --------------------------------------------------------------------------------------------------
# Copyright (c) Lukas Vik. All rights reserved.
#
# This file is part of the tsfpga project, a project platform for modern FPGA development.
# https://tsfpga.com
# https://github.com/tsfpga/tsfpga
# --------------------------------------------------------------------------------------------------

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class MssConfiguration:
    """
    Represents a Microcontroller Subsystem (MSS) configuration that shall be generated and
    imported into a Libero SoC project.

    See :meth:`.LiberoTcl._add_mss_components` for more information about the mechanism used.

    .. warning::
        This has been developed against reference designs published by Microchip on GitHub
        (e.g. the PolarFire SoC Icicle Kit reference design), not against a real Libero SoC or
        MSS Configurator installation. Confirmed for PolarFire SoC only.
    """

    def __init__(
        self,
        cfg_file: Path,
        name: str | None = None,
        output_folder: Path | None = None,
    ) -> None:
        """
        Arguments:
            cfg_file: Path to a ``.cfg`` configuration file, as saved by the standalone MSS
                Configurator GUI (e.g. ``pfsoc_mss`` for PolarFire SoC).
            name: The module name that was used when the ``.cfg`` file was created/saved in the
                MSS Configurator. This name is used to construct the file name of the generated
                ``.cxz`` component (``<name>.cxz``), which is later imported into the Libero SoC
                project.

                If not given, it is assumed to be the same as the ``.cfg`` file name (without
                suffix), which is the case as long as the ``.cfg`` file has not been renamed
                after being saved from the MSS Configurator.
            output_folder: Folder where the MSS Configurator will write its generated files
                (``.cxz``, ``.xml``, ``.html`` report).
                If not given, a folder will be picked automatically based on the Libero SoC
                project folder and this configuration's ``name``.
        """
        self.cfg_file = cfg_file
        self.name = name if name is not None else cfg_file.stem
        self.output_folder = output_folder

    def __str__(self) -> str:
        return f"{self.__class__.__name__}:{self.name}:{self.cfg_file}"
