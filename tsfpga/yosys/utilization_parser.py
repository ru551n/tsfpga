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

# The design is always flattened (see 'YosysNetlistBuild._get_synth_command') before this report
# is generated, so there will only ever be a single module in the report, and its cell list will
# contain the primitive counts for the whole design.
_CELLS_HEADER_RE = re.compile(r"^(\d+)\s+cells$")
_CELL_COUNT_RE = re.compile(r"^(\d+)\s+(\S+)$")

# Not a real hardware primitive. Yosys debug/scope bookkeeping cell that shall be ignored.
_IGNORED_CELLS = frozenset(["$scopeinfo"])

# Mapping of aggregated resource names to the prefix of the Yosys/Xilinx primitive cell names
# that shall be summed up to get that number.
# The aggregated names are chosen to match the ones used in the Vivado utilization report (see
# :mod:`.vivado.build_result_checker`), so that the same build result checkers can be reused for
# Yosys builds.
_AGGREGATE_NAME_PREFIXES = {
    "Total LUTs": "LUT",
    "FFs": "FD",
    "RAMB36": "RAMB36",
    "RAMB18": "RAMB18",
    "DSP Blocks": "DSP",
    "SRLs": "SRL",
}


class YosysUtilizationParser:
    """
    Used for parsing the resource utilization report produced by the Yosys ``stat`` command.
    """

    @staticmethod
    def get_size(report: str) -> dict[str, int]:
        """
        Arguments:
            report: The text printed to the console (or a log file) by the Yosys ``stat``
                command.

        Return:
            A dictionary with the resource utilization of the design.
            Contains the raw count of each cell primitive used in the design, as well as a
            handful of aggregated counts (e.g. ``"Total LUTs"``) using the same naming convention
            as the Vivado utilization report.
        """
        primitive_counts = YosysUtilizationParser._parse_cell_counts(report=report)

        result: dict[str, int] = dict(primitive_counts)
        for aggregate_name, prefix in _AGGREGATE_NAME_PREFIXES.items():
            result[aggregate_name] = sum(
                count for name, count in primitive_counts.items() if name.startswith(prefix)
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
