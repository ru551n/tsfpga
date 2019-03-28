-- -----------------------------------------------------------------------------
-- Copyright (c) Lukas Vik. All rights reserved.
-- -----------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library vunit_lib;
use vunit_lib.memory_pkg.all;
context vunit_lib.vunit_context;
context vunit_lib.vc_context;

library osvvm;
use osvvm.RandomPkg.all;

library bfm;

use work.axi_pkg.all;
use work.axil_pkg.all;


entity tb_axil_cdc is
  generic (
    master_clk_fast : boolean := false;
    slave_clk_fast : boolean := false;
    runner_cfg : string
  );
end entity;

architecture tb of tb_axil_cdc is

  constant data_width : integer := 32;
  constant num_words : integer := 2048;

  constant clk_fast_period : time := 3 ns;
  constant clk_slow_period : time := 7 ns;

  signal clk_master, clk_slave : std_logic := '0';

  signal master_m2s, slave_m2s : axil_m2s_t;
  signal master_s2m, slave_s2m : axil_s2m_t;

  constant axil_master_master : bus_master_t := new_bus(data_length => data_width, address_length => master_m2s.read.ar.addr'length);

  constant memory : memory_t := new_memory;
  constant axil_slave_slave : axi_slave_t := new_axi_slave(address_fifo_depth => 1, memory => memory);

begin

  test_runner_watchdog(runner, 1 ms);

  clk_master_gen : if master_clk_fast generate
    clk_master <= not clk_master after clk_fast_period / 2;
  else generate
    clk_master <= not clk_master after clk_slow_period / 2;
  end generate;

  clk_slave_gen : if slave_clk_fast generate
    clk_slave <= not clk_slave after clk_fast_period / 2;
  else generate
    clk_slave <= not clk_slave after clk_slow_period / 2;
  end generate;


  ------------------------------------------------------------------------------
  main : process
    variable rnd : RandomPType;
    variable data : std_logic_vector(data_width - 1 downto 0);
    variable address : integer;
    variable buf : buffer_t;
  begin
    test_runner_setup(runner, runner_cfg);
    rnd.InitSeed(rnd'instance_name);

    buf := allocate(memory, 4 * num_words);

    for idx in 0 to num_words - 1 loop
      address := 4 * idx;
      data := rnd.RandSlv(data'length);

       -- Call is non-blocking. I.e. we will build up a queue of writes.
      write_bus(net, axil_master_master, address, data);
      set_expected_word(memory, address, data);
      wait until rising_edge(clk_master);
    end loop;

    for idx in 0 to num_words - 1 loop
      address := 4 * idx;
      data := read_word(memory, address, 4);

      check_bus(net, axil_master_master, address, data);
    end loop;

    test_runner_cleanup(runner);
  end process;


  ------------------------------------------------------------------------------
  axil_master_inst : entity bfm.axil_master
    generic map (
      bus_handle => axil_master_master
    )
    port map (
      clk => clk_master,

      axil_m2s => master_m2s,
      axil_s2m => master_s2m
    );


  ------------------------------------------------------------------------------
  axil_slave_inst : entity bfm.axil_slave
  generic map (
    axi_slave => axil_slave_slave,
    data_width => data_width
  )
  port map (
    clk => clk_slave,

    axil_m2s => slave_m2s,
    axil_s2m => slave_s2m
  );


  ------------------------------------------------------------------------------
  dut : entity work.axil_cdc
    generic map (
      data_width => data_width
    )
    port map (
      clk_master => clk_master,
      master_m2s => master_m2s,
      master_s2m => master_s2m,

      clk_slave => clk_slave,
      slave_m2s => slave_m2s,
      slave_s2m => slave_s2m
    );

end architecture;
