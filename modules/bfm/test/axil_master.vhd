library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library math;
use math.math_pkg.all;

library axi;
use axi.axil_pkg.all;

library vunit_lib;
use vunit_lib.bus_master_pkg.all;
context vunit_lib.vunit_context;


entity axil_master is
  generic (
    bus_handle : bus_master_t
  );
  port (
    clk : in std_logic;

    axil_read_m2s : out axil_read_m2s_t := axil_read_m2s_init;
    axil_read_s2m : in axil_read_s2m_t := axil_read_s2m_init;

    axil_write_m2s : out axil_write_m2s_t := axil_write_m2s_init;
    axil_write_s2m : in axil_write_s2m_t := axil_write_s2m_init
  );
end entity;

architecture a of axil_master is

  signal rdata, wdata : std_logic_vector(data_length(bus_handle) - 1 downto 0);
  signal wstrb : std_logic_vector(byte_enable_length(bus_handle) - 1 downto 0);

begin

  ------------------------------------------------------------------------------
  rdata <= axil_read_s2m.r.data(rdata'range);

  axil_write_m2s.w.data(wdata'range) <= wdata;
  axil_write_m2s.w.strb(wstrb'range) <= wstrb;


  ------------------------------------------------------------------------------
  axi_lite_master_inst : entity vunit_lib.axi_lite_master
  generic map (
    bus_handle => bus_handle
  )
  port map (
    aclk => clk,

    arready => axil_read_s2m.ar.ready,
    arvalid => axil_read_m2s.ar.valid,
    araddr => axil_read_m2s.ar.addr,

    rready => axil_read_m2s.r.ready,
    rvalid => axil_read_s2m.r.valid,
    rdata => rdata,
    rresp => axil_read_s2m.r.resp,

    awready => axil_write_s2m.aw.ready,
    awvalid => axil_write_m2s.aw.valid,
    awaddr => axil_write_m2s.aw.addr,

    wready => axil_write_s2m.w.ready,
    wvalid => axil_write_m2s.w.valid,
    wdata => wdata,
    wstrb => wstrb,

    bready => axil_write_m2s.b.ready,
    bvalid => axil_write_s2m.b.valid,
    bresp => axil_write_s2m.b.resp
  );

end architecture;