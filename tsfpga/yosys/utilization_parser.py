# --------------------------------------------------------------------------------------------------
# Copyright (c) Lukas Vik. All rights reserved.
#
# This file is part of the tsfpga project, a project platform for modern FPGA development.
# https://tsfpga.com
# https://github.com/tsfpga/tsfpga
# --------------------------------------------------------------------------------------------------

from __future__ import annotations

import re
from collections import OrderedDict
from typing import ClassVar

# The design is always flattened (see 'YosysNetlistBuild._get_synth_command') before this report
# is generated, so there will only ever be a single module in the report, and its cell list will
# contain the primitive counts for the whole design.
_CELLS_HEADER_RE = re.compile(r"^(\d+)\s+cells$")
_CELL_COUNT_RE = re.compile(r"^(\d+)\s+(\S+)$")

# Not a real hardware primitive. Yosys debug/scope bookkeeping cell that shall be ignored.
_IGNORED_CELLS = frozenset(["$scopeinfo"])


class YosysUtilizationParser:
    """
    Used for parsing the resource utilization report produced by the Yosys ``stat`` command.

    Since the raw Yosys cell names depend entirely on which ``synth_*`` command was used, this
    class can also compute a handful of aggregated, architecture-independent resource counts
    (e.g. ``"Total LUTs"``), given a mapping of aggregated resource names to a regular expression
    that shall be matched (using :func:`re.match`) against the raw primitive cell names.

    A ready-made mapping is provided for each of the architectures supported by
    :mod:`.yosys.project` (:attr:`.XILINX_RESOURCE_NAME_PATTERNS`,
    :attr:`.INTEL_RESOURCE_NAME_PATTERNS`, :attr:`.MICROCHIP_RESOURCE_NAME_PATTERNS`).
    The aggregated names are chosen to match the ones used in the Vivado utilization report (see
    :mod:`.vivado.build_result_checker`) where applicable, so that the same build result checkers
    can be reused for Yosys builds.
    """

    #: Resource name patterns for a design synthesized with the Yosys ``synth_xilinx`` command.
    XILINX_RESOURCE_NAME_PATTERNS: ClassVar[dict[str, str]] = {
        "Total LUTs": "LUT",
        "FFs": "FD",
        "RAMB36": "RAMB36",
        "RAMB18": "RAMB18",
        "Block RAMs": "RAMB",
        "DSP Blocks": "DSP",
        "SRLs": "SRL",
    }

    #: Resource name patterns for a design synthesized with the Yosys ``synth_intel`` command
    #: (i.e. targeting the MAX10, Cyclone IV, Cyclone IV E or Cyclone 10 LP families).
    INTEL_RESOURCE_NAME_PATTERNS: ClassVar[dict[str, str]] = {
        "Total LUTs": r".*_lcell_comb$",
        "FFs": r"dffeas$",
        "Block RAMs": r"altsyncram$",
        "DSP Blocks": r".*_mac_(mult|out)$",
    }

    #: Resource name patterns for a design synthesized with the Yosys ``synth_microchip``
    #: command (i.e. targeting the PolarFire family).
    MICROCHIP_RESOURCE_NAME_PATTERNS: ClassVar[dict[str, str]] = {
        "Total LUTs": r"CFG\d$",
        "FFs": r"SLE$",
        "Block RAMs": r"RAM(1K20|64[xX]12)$",
        "DSP Blocks": r"MACC_PA$",
    }

    @staticmethod
    def get_size(
        report: str, resource_name_patterns: dict[str, str] | None = None
    ) -> dict[str, int]:
        """
        Arguments:
            report: The text printed to the console (or a log file) by the Yosys ``stat``
                command.
            resource_name_patterns: Optional mapping of aggregated resource names (e.g.
                ``"Total LUTs"``) to a regular expression that is matched, using
                :func:`re.match`, against the raw primitive cell names to decide which cells
                shall be summed up to get that number.
                See e.g. :attr:`.XILINX_RESOURCE_NAME_PATTERNS`.
                If not given, no aggregated counts are computed; only the raw cell counts are
                returned.

        Return:
            A dictionary with the resource utilization of the design.
            Contains the raw count of each cell primitive used in the design, as well as the
            aggregated counts (e.g. ``"Total LUTs"``) requested via ``resource_name_patterns``,
            if any.
        """
        primitive_counts = YosysUtilizationParser._parse_cell_counts(report=report)

        result: dict[str, int] = dict(primitive_counts)
        if resource_name_patterns:
            for aggregate_name, pattern in resource_name_patterns.items():
                result[aggregate_name] = sum(
                    count for name, count in primitive_counts.items() if re.match(pattern, name)
                )

        return result

    @staticmethod
    def _parse_cell_counts(report: str) -> dict[str, int]:
        result: OrderedDict[str, int] = OrderedDict()
        in_cell_list = False

        for line in report.splitlines():
            stripped_line = line.strip()

            if _CELLS_HEADER_RE.match(stripped_line):
                in_cell_list = True
                continue

            if not in_cell_list:
                continue

            match = _CELL_COUNT_RE.match(stripped_line)
            if match is None:
                # Blank line, or something else. The cell list has ended.
                break

            count, name = match.groups()
            if name in _IGNORED_CELLS:
                continue

            result[name] = result.get(name, 0) + int(count)

        return result
