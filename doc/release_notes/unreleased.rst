Breaking changes

* Update/simplify :class:`.GitSimulationSubset` to use new test pattern feature in VUnit 6.0.0.
* Move project filtering from :class:`.BuildProjectList` constructor
  to :func:`.get_build_project_list`.

Requires VUnit version 5.0.0.dev6 or later.

Added

* Add :class:`.YosysNetlistBuild`, :class:`.YosysXilinxNetlistBuild`,
  :class:`.YosysIntelNetlistBuild` and :class:`.YosysMicrochipNetlistBuild` for running
  :ref:`netlist builds <yosys_netlist_build>` with Yosys and the ``ghdl-yosys-plugin``,
  as an open-source alternative to :class:`.VivadoNetlistProject`.
* Add :class:`.BlockRams` build result checker for a generic, architecture-independent block RAM
  count, usable with any of the ``Yosys*NetlistBuild`` classes above.
* Add support for mixed VHDL/Verilog/SystemVerilog designs in the ``Yosys*NetlistBuild`` classes
  above, where a VHDL top level instantiates unbound Verilog/SystemVerilog modules.
* Add support for a Verilog/SystemVerilog top level (or a design with no VHDL top level at all)
  in the ``Yosys*NetlistBuild`` classes above, via the new ``vhdl_entities`` argument to
  :meth:`.YosysNetlistBuild.__init__`.
* Auto-detect the GHDL "library prefix" needed by the ``ghdl-yosys-plugin`` in the
  ``Yosys*NetlistBuild`` classes above, by calling ``ghdl --disp-config``. The ``ghdl_prefix``
  argument to :meth:`.YosysNetlistBuild.__init__` is now only needed to override this.
