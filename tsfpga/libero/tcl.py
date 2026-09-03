# --------------------------------------------------------------------------------------------------
# Copyright (c) Lukas Vik. All rights reserved.
#
# This file is part of the tsfpga project, a project platform for modern FPGA development.
# https://tsfpga.com
# https://github.com/tsfpga/tsfpga
# --------------------------------------------------------------------------------------------------

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tsfpga.vivado.common import to_tcl_path

from .generics import get_libero_tcl_generic_value

if TYPE_CHECKING:
    from pathlib import Path

    from tsfpga.build_step_tcl_hook import BuildStepTclHook
    from tsfpga.constraint import Constraint
    from tsfpga.module_list import ModuleList
    from tsfpga.vivado.generics import BitVectorGenericValue, StringGenericValue


class LiberoTcl:
    """
    Class with methods for translating a set of sources into Libero SoC TCL.

    .. note::
        This has been developed against the Libero SoC Tcl command reference documentation only.
        It has **not** been verified against a real Libero SoC installation.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def create(  # noqa: PLR0913
        self,
        project_folder: Path,
        modules: ModuleList,
        family: str,
        die: str,
        package: str,
        top: str,
        speed: str = "-1",
        die_voltage: str = "1.0",
        hdl: str = "VHDL",
        constraints: list[Constraint] | None = None,
        tcl_sources: list[Path] | None = None,
        other_arguments: dict[str, Any] | None = None,
    ) -> str:
        other_arguments = {} if other_arguments is None else other_arguments

        tcl = f"""\
new_project \
-location {{{to_tcl_path(project_folder)}}} \
-name {{{self.name}}} \
-hdl {{{hdl}}} \
-family {{{family}}} \
-die {{{die}}} \
-package {{{package}}} \
-speed {{{speed}}} \
-die_voltage {{{die_voltage}}}

"""
        tcl += self._add_module_source_files(modules=modules, other_arguments=other_arguments)
        tcl += self._add_tcl_sources(tcl_sources)

        tcl += f"""
# ------------------------------------------------------------------------------
set_root -module {{{top}::work}}

"""

        constraints = list(
            self._iterate_constraints(
                modules=modules, constraints=constraints, other_arguments=other_arguments
            )
        )
        tcl += self._add_constraints(top=top, constraints=constraints)

        tcl += """
# ------------------------------------------------------------------------------
save_project
"""
        return tcl

    def _add_module_source_files(self, modules: ModuleList, other_arguments: dict[str, Any]) -> str:
        hdl_files = []
        for module in modules:
            hdl_files += [
                hdl_file.path for hdl_file in module.get_synthesis_files(**other_arguments)
            ]

        if not hdl_files:
            return ""

        tcl = """
# ------------------------------------------------------------------------------
import_files \\
"""
        tcl += " \\\n".join(f"-hdl_source {{{to_tcl_path(hdl_file)}}}" for hdl_file in hdl_files)

        return f"{tcl}\n\n"

    @staticmethod
    def _add_tcl_sources(tcl_sources: list[Path] | None) -> str:
        if tcl_sources is None or len(tcl_sources) == 0:
            return ""

        tcl = """
# ------------------------------------------------------------------------------
"""
        for tcl_source_file in tcl_sources:
            tcl += f"source -notrace {{{to_tcl_path(tcl_source_file)}}}\n"

        return f"{tcl}\n"

    @staticmethod
    def _add_generics(
        generics: dict[str, bool | float | StringGenericValue | BitVectorGenericValue] | None,
        hdl: str,
    ) -> str:
        """
        Set generics/parameters right before running synthesis.

        .. warning::
            This has been developed against Libero SoC Tcl documentation and support articles
            only. It has **not** been verified against a real Libero SoC installation.

            Libero SoC does not have a project-wide "generic override" mechanism comparable to
            Vivado's ``set_property generic``. Instead, the value of a top-level HDL
            generic/parameter can be overridden right before synthesis using
            ``set_option -hdl_param -set <name> <value>``, as documented in a few Microchip
            support articles. This method emits that command for each generic, right before the
            ``run_tool -name {SYNTHESIZE}`` call.

            Only ``hdl="VHDL"`` is supported. Verilog parameter literal syntax has not been
            investigated, since it likely differs from VHDL's and no reference example was found.
        """
        if not generics:
            return ""

        if hdl != "VHDL":
            raise NotImplementedError(
                "Setting generics is only supported for hdl='VHDL' by the Libero SoC plugin. "
                "See 'LiberoTcl._add_generics()' for more information."
            )

        tcl = """
# ------------------------------------------------------------------------------
"""
        for name, value in generics.items():
            value_tcl_formatted = get_libero_tcl_generic_value(value=value)
            tcl += f"set_option -hdl_param -set {name} {value_tcl_formatted}\n"

        return f"{tcl}\n"

    @staticmethod
    def _iterate_constraints(
        modules: ModuleList,
        constraints: list[Constraint] | None,
        other_arguments: dict[str, Any],
    ) -> list[Constraint]:
        result = []
        for module in modules:
            result += module.get_scoped_constraints(**other_arguments)

        if constraints is not None:
            result += constraints

        return result

    @staticmethod
    def _add_constraints(top: str, constraints: list[Constraint]) -> str:
        """
        .. note::
            Both ``.sdc`` timing constraints and ``.pdc`` pin/floorplanning constraints are
            supported.

            For a ``.pdc`` file, whether it is an I/O constraint file (``-io_pdc``) or a
            floorplanning constraint file (``-fp_pdc``) is guessed from the file name: a file
            whose name (without suffix) ends with ``"_fp"`` is treated as a floorplanning
            constraint, while every other ``.pdc`` file is treated as an I/O constraint.
            This is a heuristic based on the naming convention used in Microchip's own example
            projects, and has **not** been verified against a real Libero SoC installation.

            A ``.pdc`` file is only associated with the ``PLACEROUTE`` tool, since ``.pdc``
            constraints are not consumed by ``SYNTHESIZE``/``VERIFYTIMING`` (unlike ``.sdc``).
            The ``used_in_synthesis``/``used_in_implementation`` flags are hence ignored for
            ``.pdc`` files, apart from ``used_in_implementation`` gating whether the file is
            associated with ``PLACEROUTE`` at all.

            Scoped constraints and a non-default processing order are **not yet supported**,
            since Libero SoC has no directly corresponding mechanism.
        """
        if len(constraints) == 0:
            return ""

        tcl = """
# ------------------------------------------------------------------------------
"""
        module_argument = f"-module {{{top}::work}}"

        for constraint in constraints:
            if constraint.ref is not None:
                raise NotImplementedError(
                    f"Scoped constraints are not yet supported by the Libero SoC plugin: "
                    f"{constraint.file}"
                )
            if constraint.processing_order != "normal":
                raise NotImplementedError(
                    "A non-default 'processing_order' is not yet supported by the "
                    f"Libero SoC plugin: {constraint.file}"
                )

            constraint_file = to_tcl_path(constraint.file)

            if constraint_file.endswith(".sdc"):
                tcl += LiberoTcl._sdc_constraint_tcl(
                    constraint=constraint,
                    constraint_file=constraint_file,
                    module_argument=module_argument,
                )
            elif constraint_file.endswith(".pdc"):
                tcl += LiberoTcl._pdc_constraint_tcl(
                    constraint=constraint,
                    constraint_file=constraint_file,
                    module_argument=module_argument,
                )
            else:
                raise NotImplementedError(
                    "Only '.sdc' and '.pdc' constraint files are supported by the Libero SoC "
                    f"plugin at this time. Got: {constraint.file}"
                )

        return f"{tcl}\n"

    @staticmethod
    def _sdc_constraint_tcl(
        constraint: Constraint, constraint_file: str, module_argument: str
    ) -> str:
        tcl = f"import_files -sdc {{{constraint_file}}}\n"

        if constraint.used_in_synthesis:
            tcl += (
                f"organize_tool_files -tool {{SYNTHESIZE}} -file {{{constraint_file}}} "
                f"{module_argument} -input_type {{constraint}}\n"
            )

        if constraint.used_in_implementation:
            for tool_name in ("PLACEROUTE", "VERIFYTIMING"):
                tcl += (
                    f"organize_tool_files -tool {{{tool_name}}} -file {{{constraint_file}}} "
                    f"{module_argument} -input_type {{constraint}}\n"
                )

        return tcl

    @staticmethod
    def _pdc_constraint_tcl(
        constraint: Constraint, constraint_file: str, module_argument: str
    ) -> str:
        pdc_flag = "-fp_pdc" if constraint.file.stem.endswith("_fp") else "-io_pdc"
        tcl = f"import_files {pdc_flag} {{{constraint_file}}}\n"

        if constraint.used_in_implementation:
            tcl += (
                f"organize_tool_files -tool {{PLACEROUTE}} -file {{{constraint_file}}} "
                f"{module_argument} -input_type {{constraint}}\n"
            )

        return tcl

    def build(  # noqa: PLR0913
        self,
        project_file: Path,
        top: str,
        output_path: Path | None,
        build_step_hooks: list[BuildStepTclHook] | None = None,
        generics: dict[str, bool | float | StringGenericValue | BitVectorGenericValue]
        | None = None,
        hdl: str = "VHDL",
        synth_only: bool = False,
    ) -> str:
        hooks_by_step = self._organize_build_step_hooks(build_step_hooks)

        tcl = f"open_project {{{to_tcl_path(project_file)}}}\n"

        tcl += self._add_generics(generics=generics, hdl=hdl)
        tcl += self._run_tool(name="SYNTHESIZE", hooks_by_step=hooks_by_step)

        if not synth_only:
            if output_path is None:
                raise ValueError("Output path must be set for implementation builds.")

            tcl += self._run_tool(name="PLACEROUTE", hooks_by_step=hooks_by_step)
            tcl += self._run_tool(name="VERIFYTIMING", hooks_by_step=hooks_by_step)
            tcl += self._run_tool(name="VERIFYPOWER", hooks_by_step=hooks_by_step)
            tcl += self._run_tool(name="GENERATEPROGRAMMINGDATA", hooks_by_step=hooks_by_step)
            tcl += self._run_tool(name="GENERATEPROGRAMMINGFILE", hooks_by_step=hooks_by_step)

            export_dir = to_tcl_path(output_path)
            tcl += f"""
# ------------------------------------------------------------------------------
export_bitstream_file -file_name {{{top}}} -export_dir {{{export_dir}}} -format {{STP}}

"""

        tcl += """
# ------------------------------------------------------------------------------
save_project
"""
        return tcl

    @staticmethod
    def _organize_build_step_hooks(
        build_step_hooks: list[BuildStepTclHook] | None,
    ) -> dict[str, list[Path]]:
        """
        Reorganize the flat hook list into a ``{hook step: [tcl files]}`` mapping for lookup
        when building the ``run_tool`` sequence.

        Unlike Vivado, Libero SoC has no native per-step Tcl hook property.
        Since tsfpga fully controls the generated build script, the hooks are instead emulated by
        ``source``-ing the hook file immediately before/after the relevant ``run_tool`` call.
        Use hook step names ``"<TOOL NAME>.PRE"``/``"<TOOL NAME>.POST"``,
        e.g. ``"SYNTHESIZE.PRE"`` or ``"PLACEROUTE.POST"``.
        """
        result: dict[str, list[Path]] = {}
        for build_step_hook in build_step_hooks or []:
            result.setdefault(build_step_hook.hook_step, []).append(build_step_hook.tcl_file)

        return result

    @staticmethod
    def _run_tool(name: str, hooks_by_step: dict[str, list[Path]]) -> str:
        tcl = """
# ------------------------------------------------------------------------------
"""
        for hook_file in hooks_by_step.get(f"{name}.PRE", []):
            tcl += f"source -notrace {{{to_tcl_path(hook_file)}}}\n"

        tcl += f"run_tool -name {{{name}}}\n"

        for hook_file in hooks_by_step.get(f"{name}.POST", []):
            tcl += f"source -notrace {{{to_tcl_path(hook_file)}}}\n"

        return tcl
