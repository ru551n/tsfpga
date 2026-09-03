# --------------------------------------------------------------------------------------------------
# Copyright (c) Lukas Vik. All rights reserved.
#
# This file is part of the tsfpga project, a project platform for modern FPGA development.
# https://tsfpga.com
# https://github.com/tsfpga/tsfpga
# --------------------------------------------------------------------------------------------------

from __future__ import annotations

from tsfpga.vivado.generics import BitVectorGenericValue, StringGenericValue


def get_libero_tcl_generic_value(
    value: bool | float | StringGenericValue | BitVectorGenericValue,
) -> str:
    """
    Convert generic/parameter values of different types to VHDL literal syntax, for use with
    Libero SoC's ``set_option -hdl_param -set <name> <value>`` mechanism.

    .. warning::
        This has been developed against Libero SoC Tcl documentation and support articles only.
        It has **not** been verified against a real Libero SoC installation.
        Only VHDL literal syntax is supported.
        See :func:`.LiberoTcl._add_generics` for more information.

    Arguments:
        value: A generic value of native Python type.

    Return:
        The ``value`` formatted as a VHDL literal, suitable for TCL.
    """
    # Note that bool is a sub-class of int in Python, so check for bool must be first.
    if isinstance(value, bool):
        # VHDL boolean literal.
        return "TRUE" if value else "FALSE"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        return str(value)

    if isinstance(value, BitVectorGenericValue):
        # VHDL bit_vector/std_logic_vector literal.
        return f'"{value.value}"'

    if isinstance(value, StringGenericValue):
        # VHDL string literal.
        return f'"{value.value}"'

    message = f'Unsupported type for generic. Got type="{type(value)}", value="{value}".'

    # When the type is a string, we can be a little more helpful and indicate what types shall
    # be used instead.
    if isinstance(value, str):
        message += (
            " Please use either of the explicit types StringGenericValue or BitVectorGenericValue."
        )

    raise TypeError(message)
