# --------------------------------------------------------------------------------------------------
# Copyright (c) Lukas Vik. All rights reserved.
#
# This file is part of the tsfpga project, a project platform for modern FPGA development.
# https://tsfpga.com
# https://github.com/tsfpga/tsfpga
# --------------------------------------------------------------------------------------------------

from __future__ import annotations

import random
from typing import Any

from tsfpga.libero.project import LiberoProject


class TsfpgaExampleLiberoProject(LiberoProject):
    """
    Example Libero SoC project class.
    Shows how to override and extend the base behavior.

    .. warning::
        This class, along with the rest of the :mod:`tsfpga.libero` plugin, has been developed
        against the Libero SoC Tcl command reference documentation only.
        It has **not** been verified against a real Libero SoC installation.
        See :class:`.LiberoProject` for known limitations.

    Unlike :class:`.VivadoProject`, Libero SoC has no project-level mechanism for overriding
    generic/parameter values at project-create time (see :class:`.LiberoProject` and
    :meth:`.LiberoTcl._add_generics`).
    Generics are instead applied at build time, right before synthesis.
    Hence, unlike :class:`.TsfpgaExampleVivadoProject`, this class only needs to set the
    ``build_id`` generic in :meth:`.pre_build`, not in ``pre_create``.
    """

    def pre_build(
        self,
        generics: dict[str, Any],
        **kwargs: Any,  # noqa: ANN401
    ) -> bool:
        """
        Is called right before the Libero SoC system call that builds the project.
        Override parent method to add custom behavior.
        """
        self._set_build_id_generic(generics=generics)

        return super().pre_build(generics=generics, kwargs=kwargs)

    def _set_build_id_generic(self, generics: dict[str, Any]) -> None:
        """
        Set a random value.
        """
        # Set a suitable range so the generic can be handled as a VHDL 'natural'.
        # Does not need to be cryptographically secure.
        generics["build_id"] = random.randint(1, 2**25 - 1)  # noqa: S311
