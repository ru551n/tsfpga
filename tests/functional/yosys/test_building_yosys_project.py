# --------------------------------------------------------------------------------------------------
# Copyright (c) Lukas Vik. All rights reserved.
#
# This file is part of the tsfpga project, a project platform for modern FPGA development.
# https://tsfpga.com
# https://github.com/tsfpga/tsfpga
# --------------------------------------------------------------------------------------------------

import os
import shutil
from pathlib import Path

import pytest

from tsfpga.module import get_modules
from tsfpga.system_utils import create_file
from tsfpga.test.test_utils import file_contains_string
from tsfpga.vivado.build_result_checker import EqualTo, GreaterThan, LessThan, TotalLuts
from tsfpga.yosys.project import YosysNetlistBuild, YosysXilinxNetlistBuild

# Path to the 'ghdl-yosys-plugin' module (typically named 'ghdl.so').
# Can be left unset if the plugin is already available to Yosys without explicitly loading it
# (e.g. if it has been installed in the Yosys plugin directory).
GHDL_PLUGIN_PATH = (
    Path(os.environ["TSFPGA_GHDL_PLUGIN_PATH"]) if "TSFPGA_GHDL_PLUGIN_PATH" in os.environ else None
)

# Value for the 'GHDL_PREFIX' environment variable, see 'YosysNetlistBuild' docstring.
# Can be left unset if GHDL is installed in a standard system location.
GHDL_PREFIX = Path(os.environ["TSFPGA_GHDL_PREFIX"]) if "TSFPGA_GHDL_PREFIX" in os.environ else None

# This whole test suite requires GHDL and Yosys, with the 'ghdl-yosys-plugin', to be installed
# on the machine that runs the tests.
pytestmark = pytest.mark.skipif(
    shutil.which("ghdl") is None or shutil.which("yosys") is None,
    reason="GHDL and/or Yosys is not available on the PATH",
)


@pytest.fixture
def basic_project_test(tmp_path):
    class BasicProjectTest:
        def __init__(self):
            self.module_folder = tmp_path / "modules" / "apa"
            self.project_folder = tmp_path / "yosys"

            self.top_file = self.create_top_file()

            self.modules = get_modules(modules_folder=self.module_folder.parent)
            # Target Xilinx primitives, so that the utilization report contains the LUT/FF
            # counts that the 'tsfpga.vivado.build_result_checker' checkers expect.
            self.proj = YosysXilinxNetlistBuild(
                family="xc7",
                name="test_proj",
                modules=self.modules,
                build_result_checkers=[TotalLuts(LessThan(100))],
                ghdl_plugin_path=GHDL_PLUGIN_PATH,
                ghdl_prefix=GHDL_PREFIX,
            )

        @property
        def script_file(self):
            """
            The Yosys command script that should exist after a build.
            """
            return self.proj.project_file(project_path=self.project_folder)

        @property
        def utilization_report_file(self):
            """
            The Yosys utilization report that should exist after a build.
            """
            return self.project_folder / f"{self.proj.name}_utilization.txt"

        def create_top_file(self, width: int = 8):
            top = f"""
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;


entity test_proj_top is
  generic (
    width : positive := {width}
  );
  port (
    clk : in std_ulogic;
    increment : in std_ulogic;
    count : out unsigned(width - 1 downto 0);
    flag : out std_ulogic
  );
end entity;

architecture a of test_proj_top is
  signal count_int : unsigned(width - 1 downto 0) := (others => '0');
begin

  count <= count_int;

  -- Some combinational logic that will always require LUTs to implement, regardless of how
  -- the counter's carry chain above is optimized.
  flag <=
    (count_int(0) and count_int(1))
    or (count_int(2) and not increment)
    or (count_int(3) xor count_int(0));

  main : process
  begin
    wait until rising_edge(clk);

    if increment = '1' then
      count_int <= count_int + 1;
    end if;
  end process;

end architecture;
"""
            return create_file(self.module_folder / "src" / "test_proj_top.vhd", top)

        def create_yosys_project(self):
            assert self.proj.create(self.project_folder)
            assert self._get_ghdl_workdir().exists()

        def _get_ghdl_workdir(self):
            return self.project_folder / "ghdl"

    return BasicProjectTest()


def test_create_project(basic_project_test):
    basic_project_test.create_yosys_project()


def test_synth_project(basic_project_test):
    basic_project_test.create_yosys_project()

    build_result = basic_project_test.proj.build(basic_project_test.project_folder)
    assert build_result.success
    assert basic_project_test.script_file.exists()
    assert basic_project_test.utilization_report_file.exists()
    assert build_result.synthesis_size["Total LUTs"] < 100


def test_build_without_create_should_fail(basic_project_test):
    with pytest.raises(ValueError, match="does not exist in the specified location"):
        basic_project_test.proj.build(basic_project_test.project_folder)


def test_synth_should_fail_if_source_code_does_not_compile(basic_project_test):
    create_file(
        basic_project_test.top_file,
        """
this is not valid VHDL code
""",
    )

    assert not basic_project_test.proj.create(basic_project_test.project_folder)


def test_build_result_checker_failure_should_fail_build(basic_project_test):
    basic_project_test.proj.build_result_checkers = [TotalLuts(EqualTo(0))]
    basic_project_test.create_yosys_project()

    build_result = basic_project_test.proj.build(basic_project_test.project_folder)
    assert not build_result.success
    # The report should still have been produced, even though the check failed.
    assert basic_project_test.utilization_report_file.exists()


def test_build_result_checker_success(basic_project_test):
    basic_project_test.proj.build_result_checkers = [
        TotalLuts(LessThan(100)),
        TotalLuts(GreaterThan(0)),
    ]
    basic_project_test.create_yosys_project()

    build_result = basic_project_test.proj.build(basic_project_test.project_folder)
    assert build_result.success


def test_build_with_generics(basic_project_test):
    basic_project_test.create_yosys_project()

    build_result = basic_project_test.proj.build(
        basic_project_test.project_folder, generics={"width": 4}
    )
    assert build_result.success
    assert file_contains_string(file=basic_project_test.script_file, string="-gwidth=4")


def test_building_plain_yosys_netlist_project(basic_project_test):
    """
    The base class targets generic Yosys primitives rather than Xilinx ones, so the
    'TotalLuts'/'Ffs' style checkers can not be used. The raw cell counts are still available.
    """
    project = YosysNetlistBuild(
        name="test_proj",
        modules=basic_project_test.modules,
        ghdl_plugin_path=GHDL_PLUGIN_PATH,
        ghdl_prefix=GHDL_PREFIX,
    )
    assert project.create(basic_project_test.project_folder)

    build_result = project.build(project_path=basic_project_test.project_folder)
    assert build_result.success
    assert sum(build_result.synthesis_size.values()) > 0
