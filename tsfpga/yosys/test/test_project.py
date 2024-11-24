from pathlib import Path
import pytest
from tsfpga.module_list import ModuleList
from tsfpga.module import BaseModule
from tsfpga.yosys.project import YosysNetlistBuild
from vunit.vhdl_standard import VHDLStandard


@pytest.fixture
def mixed_module(tmp_path):
    base_dir = tmp_path
    src = tmp_path / "src"
    src.mkdir()

    vhdl_top = src / "vhdl_top_with_mixed.vhd"
    verilog_entity = src / "verilog_module.v"
    vhdl_entity = src / "vhdl_module.vhd"

    vhdl_top_with_mixed = """\
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity vhdl_top_with_mixed is
    port(
        clk : in std_logic;
        d : in std_logic;
        q : out std_logic
    );
end entity;

architecture rtl of vhdl_top_with_mixed is
  component verilog_module is
    port(
      clk : in std_logic;
      d : in std_logic;
      q : out std_logic
    );
  end component;

  signal q_int : std_logic;
begin

  verilog_module_inst : verilog_module
  port map (
    clk => clk,
    d => d,
    q => q_int
  );

  vhdl_module : entity work.vhdl_module
  port map (
    clk => clk,
    d => q_int,
    q => q
  );
    
end architecture rtl;
"""
    vhdl_top.write_text(vhdl_top_with_mixed, encoding="utf-8")

    verilog_module = """\
module verilog_module (
    input clk,
    input d,
    output reg q
);
	always @(posedge clk) 
    begin
        q <= d;
    end
endmodule

"""
    verilog_entity.write_text(verilog_module, encoding="utf-8")

    vhdl_module = """
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity vhdl_module is
  port(
    clk : in std_logic;
    d : in std_logic;
    q : out std_logic
  );
end entity;

architecture rtl of vhdl_module is
begin

  process(clk)
  begin
    if rising_edge(clk) then
      q <= d;
    end if;
  end process;
    
end architecture;
"""
    vhdl_entity.write_text(vhdl_module, encoding="utf-8")

    return BaseModule(base_dir, library_name="hest")


@pytest.fixture
def dummy_module(tmp_path):

    base_dir = tmp_path
    src = tmp_path / "src"
    src.mkdir(parents=True)
    vhd_file = src / "hest.vhd"
    vhd_file.touch()
    verilog_file = src / "apa.v"
    verilog_file.touch()

    return BaseModule(base_dir, library_name="apa")


def test_no_modules_doesnt_find_top_level():

    proj = YosysNetlistBuild(name="foo", top="foo_top", modules=ModuleList())

    files = None
    with pytest.raises(ValueError) as exception_info:
        files = proj._get_required_synthesis_files()

        assert (
            str(exception_info.value)
            == "Could not determine top level, multiple or no files containing top level found"
        )
    assert files is None


def test_create_script(dummy_module):

    modules = ModuleList()
    modules.append(dummy_module)

    for vhdl_standard in ["1993", "2002", "2008", "2019"]:
        for synth_command in [None, "synth_xilinx"]:
            proj = YosysNetlistBuild(
                name="hest",
                modules=modules,
                top="hest",
                synth_command=synth_command,
                vhdl_standard=VHDLStandard(vhdl_standard),
            )
            script = proj._create_script()

            if synth_command:
                expected_synth = synth_command
            else:
                expected_synth = "synth"

            expected_script = f"""\
ghdl --std={vhdl_standard[2:]} --work=apa --workdir=ghdl -P=ghdl; \
{expected_synth} -top hest; \
sta"""

            assert script == expected_script


def test_create_script_with_mixed_sources(mixed_module):

    modules = ModuleList()
    modules.append(mixed_module)

    proj = YosysNetlistBuild(
        name="hest",
        modules=modules,
        top="vhdl_top_with_mixed",
        vhdl_standard=VHDLStandard("2008"),
    )
    script = proj._create_script()
    
    assert "ghdl --std=08 --work=hest --workdir=ghdl -P=ghdl;" in script
    assert "read_verilog" in script
    assert "src/verilog_module.v;" in script
    assert "synth -top vhdl_top_with_mixed;" in script
    assert "sta" in script
