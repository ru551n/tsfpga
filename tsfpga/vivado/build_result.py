# --------------------------------------------------------------------------------------------------
# Copyright (c) Lukas Vik. All rights reserved.
#
# This file is part of the tsfpga project, a project platform for modern FPGA development.
# https://tsfpga.com
# https://github.com/tsfpga/tsfpga
# --------------------------------------------------------------------------------------------------

from __future__ import annotations

# 'BuildResult' is a generic, backend-agnostic type (used by e.g. 'tsfpga.yosys.project' as well)
# that historically lived in this module. It is now defined in 'tsfpga.build_result', and
# re-exported here for backward compatibility.
from tsfpga.build_result import BuildResult  # noqa: F401
