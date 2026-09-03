# --------------------------------------------------------------------------------------------------
# Copyright (c) Lukas Vik. All rights reserved.
#
# This file is part of the tsfpga project, a project platform for modern FPGA development.
# https://tsfpga.com
# https://github.com/tsfpga/tsfpga
# --------------------------------------------------------------------------------------------------

from __future__ import annotations

from pathlib import Path

from tsfpga.constraint import Constraint
from tsfpga.examples.example_env import get_tsfpga_example_modules
from tsfpga.examples.libero.project import TsfpgaExampleLiberoProject
from tsfpga.libero.mss import MssConfiguration
from tsfpga.module import BaseModule

THIS_FILE = Path(__file__)


class Module(BaseModule):
    def get_build_projects(self) -> list[TsfpgaExampleLiberoProject]:
        # Only this module is used, so that the generated project only contains files relevant
        # to this example. This also avoids a dependency on the external 'hdl-modules'
        # repository, and avoids pulling in other tsfpga example modules that use
        # Xilinx-specific primitives (which would not be valid for a Libero SoC/Microchip
        # target).
        modules = get_tsfpga_example_modules(names_include={self.name})

        constraints = [Constraint(self.path / "pdc" / "libero_example_pinning.pdc")]

        # Demonstrates how a Microcontroller Subsystem (MSS) configuration can be generated and
        # imported into the project. See 'MssConfiguration' and
        # 'LiberoTcl._add_mss_components' for more information, including limitations.
        #
        # Note that the referenced '.cfg' file is NOT included in this repository.
        # It would need to be created and saved using the standalone MSS Configurator GUI
        # (e.g. 'pfsoc_mss' for PolarFire SoC) before this project could actually be built.
        mss_configurations = [
            MssConfiguration(cfg_file=self.path / "mss" / "libero_example_mss.cfg")
        ]

        return [
            TsfpgaExampleLiberoProject(
                name="libero_example",
                modules=modules,
                family="PolarFire",
                die="MPF300TS_ES",
                package="FCG1152",
                constraints=constraints,
                mss_configurations=mss_configurations,
                defined_at=THIS_FILE,
            )
        ]
