Breaking changes

* Update/simplify :class:`.GitSimulationSubset` to use new test pattern feature in VUnit 6.0.0.
* Move project filtering from :class:`.BuildProjectList` constructor
  to :func:`.get_build_project_list`.

Requires VUnit version 5.0.0.dev6 or later.

Added

* Add support for :ref:`netlist builds <yosys_netlist_build>` using Yosys and the
  ``ghdl-yosys-plugin``, as an open-source alternative to :class:`.VivadoNetlistProject`.
  Supports Xilinx, Intel and Microchip devices, mixed VHDL/Verilog/SystemVerilog designs, and
  generic resource counting.
* Allow :class:`.YosysNetlistBuild` projects (in addition to :class:`.VivadoProject`) to be
  returned from :meth:`.BaseModule.get_build_projects` and handled by
  :class:`.BuildProjectList`, so a project's standard build script (e.g. ``build_fpga.py``) can
  drive Yosys netlist builds the same way it drives Vivado builds.
