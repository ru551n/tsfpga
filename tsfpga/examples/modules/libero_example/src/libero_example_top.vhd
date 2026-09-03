-- -------------------------------------------------------------------------------------------------
-- Copyright (c) Lukas Vik. All rights reserved.
--
-- This file is part of the tsfpga project, a project platform for modern FPGA development.
-- https://tsfpga.com
-- https://github.com/tsfpga/tsfpga
-- -------------------------------------------------------------------------------------------------
-- Minimal, tool-agnostic top level used by the 'libero_example' build project.
-- Uses only 'ieee' library constructs, so it does not depend on the external 'hdl-modules'
-- repository, and can be used to sketch the Libero SoC build flow even without that
-- dependency available.
-- -------------------------------------------------------------------------------------------------

library ieee;
use ieee.numeric_std.all;
use ieee.std_logic_1164.all;


entity libero_example_top is
  generic (
    -- Random build ID used to distinguish between builds.
    -- Set by 'TsfpgaExampleLiberoProject.pre_build'. Given a default value so that the
    -- project can also be built manually from the Libero SoC GUI.
    build_id : natural := 0
  );
  port (
    clk : in std_ulogic;
    input : in std_ulogic;
    output : out std_ulogic := '0'
  );
end entity;

architecture a of libero_example_top is

  signal build_id_lsb : std_ulogic := '0';

begin

  build_id_lsb <= '1' when (build_id mod 2) = 1 else '0';

  ------------------------------------------------------------------------------
  pipe : process
  begin
    wait until rising_edge(clk);

    output <= input xor build_id_lsb;
  end process;

end architecture;
