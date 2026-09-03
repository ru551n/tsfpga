# --------------------------------------------------------------------------------------------------
# Copyright (c) Lukas Vik. All rights reserved.
#
# This file is part of the tsfpga project, a project platform for modern FPGA development.
# https://tsfpga.com
# https://github.com/tsfpga/tsfpga
# --------------------------------------------------------------------------------------------------

from __future__ import annotations

import os
import sys
import tempfile
from argparse import Namespace
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

from vunit.ui import VUnit

from tsfpga.system_utils import create_directory, read_file
from tsfpga.vivado.build_result import BuildResult
from tsfpga.vivado.generics import BitVectorGenericValue, StringGenericValue
from tsfpga.vivado.project import copy_and_combine_dicts

from .common import run_ghdl, run_yosys, to_yosys_path
from .utilization_parser import YosysUtilizationParser

if TYPE_CHECKING:
    from collections.abc import Iterator

    from vunit.ui.source import SourceFile

    from tsfpga.module import BaseModule
    from tsfpga.module_list import ModuleList
    from tsfpga.vivado.build_result_checker import SizeChecker


class YosysNetlistBuild:
    """
    Used for handling a synthesis-only (netlist) build of a design, using Yosys with the
    ``ghdl-yosys-plugin`` as the VHDL front end.

    Since this is a netlist build, there is no implementation (place & route) step, and hence
    no bitstream is produced.
    This is a great tool for getting quick feedback on the resource utilization of a design, or
    a sub-component of a design, during development.

    .. note::
        Requires GHDL, Yosys, and the ``ghdl-yosys-plugin`` module to be installed and
        available.
        See the `ghdl-yosys-plugin documentation
        <https://github.com/ghdl/ghdl-yosys-plugin>`__ for installation instructions.
    """

    #: Will always be ``True`` for this class, since it is a netlist build.
    is_netlist_build = True

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        name: str,
        modules: ModuleList,
        top: str | None = None,
        generics: dict[str, bool | float | StringGenericValue | BitVectorGenericValue]
        | None = None,
        build_result_checkers: list[SizeChecker] | None = None,
        synth_command: str = "synth",
        vhdl_standard: str = "08",
        ghdl_path: Path | None = None,
        yosys_path: Path | None = None,
        ghdl_plugin_path: Path | None = None,
        ghdl_prefix: Path | None = None,
        defined_at: Path | None = None,
        **other_arguments: Any,  # noqa: ANN401
    ) -> None:
        """
        Class constructor. Performs a shallow copy of the mutable arguments, so that the user
        can e.g. append items to their list after creating an object.

        Arguments:
            name: Project name.
            modules: Modules that shall be included in the build.
                Only VHDL source files are considered, since the build uses the GHDL front end.
            top: Name of top level entity.
                If left out, the top level name will be inferred from the ``name``.
            generics: A dict with generics values (name: value). Use this parameter
                for "static" generics that do not change between multiple builds of this
                project.

                Compare to the build-time generic argument in :meth:`build`.

                The generic value shall be of type

                * :class:`bool` (suitable for VHDL type ``boolean`` and ``std_logic``),
                * :class:`int` (suitable for VHDL type ``integer``, ``natural``, etc.),
                * :class:`float` (suitable for VHDL type ``real``),
                * :class:`.BitVectorGenericValue` (suitable for VHDL type ``std_logic_vector``,
                  ``unsigned``, etc.), or
                * :class:`.StringGenericValue` (suitable for VHDL type ``string``).
            build_result_checkers:
                Checkers that will be executed after a successful build. Is used to automatically
                check that e.g. resource utilization is not greater than expected.
                Since the utilization report produced by this build uses the same resource
                naming convention as the Vivado utilization report, the checkers in
                :mod:`.vivado.build_result_checker` can be used directly.
            synth_command: The Yosys ``synth*`` command that shall be used to synthesize the
                design (e.g. ``"synth"`` or ``"synth_xilinx"``).
                See :class:`.YosysXilinxNetlistBuild` for a convenient subclass that targets
                Xilinx primitives.
            vhdl_standard: The VHDL standard that shall be used by GHDL when analyzing the
                source files (e.g. ``"93"`` or ``"08"``).
            ghdl_path: Path to the GHDL executable.
                If omitted, the default location from the system PATH will be used.
            yosys_path: Path to the Yosys executable.
                If omitted, the default location from the system PATH will be used.
            ghdl_plugin_path: Path to the ``ghdl-yosys-plugin`` module (typically named
                ``ghdl.so``).
                Can be left out if the plugin is already available to Yosys without explicitly
                loading it (e.g. if it has been installed in the Yosys plugin directory).
            ghdl_prefix: Value to set the ``GHDL_PREFIX`` environment variable to when running
                Yosys with the ``ghdl-yosys-plugin``. Required on some systems, since the
                plugin does not necessarily know where to find the GHDL standard libraries
                (``std``, ``ieee``, ...) on its own. Corresponds to the "library prefix" printed
                by ``ghdl --disp-config``.
                Can be left out if the plugin already finds the libraries on its own (e.g. if
                GHDL was installed in a standard system location).
            defined_at: Optional path to the file where you defined this project.
                To get a useful ``build_fpga.py --list`` message. Is useful when you have many
                projects set up.
            other_arguments: Optional further arguments. Will not be used by tsfpga, but will
                instead be passed on to

                * :func:`BaseModule.get_synthesis_files()
                  <tsfpga.module.BaseModule.get_synthesis_files>`
                * :func:`BaseModule.pre_build() <tsfpga.module.BaseModule.pre_build>`
                * :func:`YosysNetlistBuild.pre_create`
                * :func:`YosysNetlistBuild.pre_build`
                * :func:`YosysNetlistBuild.post_build`

                along with further arguments supplied at build-time to :meth:`.create` and
                :meth:`.build`.

                .. note::
                    This is a "kwargs" style argument. You can pass any number of named arguments.
        """
        self.name = name
        self.modules = modules.copy()
        self.top = name + "_top" if top is None else top
        self.static_generics = {} if generics is None else generics.copy()
        self.build_result_checkers = (
            [] if build_result_checkers is None else build_result_checkers.copy()
        )
        self.synth_command = synth_command
        self.defined_at = defined_at
        self.other_arguments = None if other_arguments is None else other_arguments.copy()

        self._vhdl_standard = vhdl_standard
        self._ghdl_path = ghdl_path
        self._yosys_path = yosys_path
        self._ghdl_plugin_path = ghdl_plugin_path
        self._ghdl_prefix = ghdl_prefix

        # Lazily created/cached. See '_get_vunit_project' and '_get_top_level_module'.
        self._vunit_proj: VUnit | None = None
        self._top_level_module: BaseModule | None = None

    def project_file(self, project_path: Path) -> Path:
        """
        Arguments:
            project_path: A path containing a Yosys netlist build.

        Return:
            The Yosys command script of this build, in the given folder.
        """
        return project_path / f"{self.name}.ys"

    def _get_ghdl_workdir(self, project_path: Path) -> Path:
        return project_path / "ghdl"

    def _get_vunit_project(self) -> VUnit:
        if self._vunit_proj is None:
            # VUnit is only used to resolve the compile order of the VHDL source files, not to
            # run any simulations. Hence the output is placed in a throwaway temporary
            # directory, and the (rather expensive) compilation of simulation builtins is
            # skipped.
            output_path = tempfile.mkdtemp(prefix="tsfpga_yosys_vunit_")
            arguments = Namespace(
                output_path=output_path, log_level="error", no_color=True, clean=False
            )

            with _suppress_stdout():
                self._vunit_proj = VUnit.from_args(args=arguments, compile_builtins=False)

            for module in self.modules:
                vunit_library = self._vunit_proj.add_library(
                    library_name=module.library_name, allow_duplicate=True
                )
                for hdl_file in module.get_synthesis_files(
                    include_verilog_files=False, include_systemverilog_files=False
                ):
                    vunit_library.add_source_file(hdl_file.path)

        return self._vunit_proj

    def _get_top_level_module(self) -> BaseModule:
        if self._top_level_module is None:
            top_level_modules = [
                module
                for module in self.modules
                for hdl_file in module.get_synthesis_files(
                    include_verilog_files=False, include_systemverilog_files=False
                )
                if hdl_file.path.stem == self.top
            ]

            if len(top_level_modules) == 0:
                raise ValueError(f'Could not find a VHDL source file for top level "{self.top}".')
            if len(top_level_modules) > 1:
                raise ValueError(f'Found multiple VHDL source files for top level "{self.top}".')

            self._top_level_module = top_level_modules[0]

        return self._top_level_module

    def _get_top_source_file(self) -> SourceFile:
        library_name = self._get_top_level_module().library_name
        top_file_pattern = f"*/{self.top}.vhd"

        return self._get_vunit_project().get_source_file(
            top_file_pattern, library_name=library_name
        )

    def _get_synthesis_files_in_compile_order(self) -> list[tuple[str, str]]:
        """
        Return: A list of tuples ``(file_path, library_name)`` in the order they need to be
            analyzed by GHDL.
        """
        top_source_file = self._get_top_source_file()
        compile_order = self._get_vunit_project().get_implementation_subset([top_source_file])

        return [
            (Path(source_file.name).resolve().as_posix(), source_file.library.name)
            for source_file in compile_order
        ]

    def create(
        self,
        project_path: Path,
        ip_cache_path: Path | None = None,  # noqa: ARG002
        **other_arguments: Any,  # noqa: ANN401
    ) -> bool:
        """
        Analyze all the VHDL source files with GHDL, so that the design is ready to be
        elaborated and synthesized by :meth:`.build`.

        Arguments:
            project_path: Path where the GHDL analysis result shall be placed.
            ip_cache_path: Not used. Present for interface compatibility with
                :meth:`.VivadoProject.create`.
            other_arguments: Optional further arguments. Will not be used by tsfpga, but will
                instead be sent to

                * :func:`BaseModule.get_synthesis_files()
                  <tsfpga.module.BaseModule.get_synthesis_files>`
                * :func:`YosysNetlistBuild.pre_create`

                along with further ``other_arguments`` supplied to :meth:`.__init__`.

        Return:
            True if everything went well.
        """
        print(f"Creating Yosys netlist build {self.name} in {project_path}")

        # The pre-create hook might have side effects. E.g. change some register constants.
        # So we make a deep copy of the module list before the hook is called.
        self.modules = deepcopy(self.modules)

        all_arguments = copy_and_combine_dicts(self.other_arguments, other_arguments)
        if not self.pre_create(project_path=project_path, **all_arguments):
            print("ERROR: Project pre-create hook returned False. Failing the build.")
            return False

        workdir = self._get_ghdl_workdir(project_path=project_path)
        create_directory(workdir, empty=True)

        for file_path, library_name in self._get_synthesis_files_in_compile_order():
            arguments = [
                "-a",
                f"--std={self._vhdl_standard}",
                f"--workdir={workdir}",
                f"-P={workdir}",
                f"--work={library_name}",
                file_path,
            ]

            if not run_ghdl(ghdl_path=self._ghdl_path, arguments=arguments, cwd=workdir):
                print(f'ERROR: GHDL analysis failed for "{self.name}".')
                return False

        return True

    def pre_create(
        self,
        **kwargs: Any,  # noqa: ANN401, ARG002
    ) -> bool:
        """
        Override this function in a subclass if you wish to do something useful with it.
        Will be called from :meth:`.create` right before the GHDL analysis is started.

        .. Note::
            This default method does nothing. Shall be overridden by project that utilize
            this mechanism.

        Arguments:
            kwargs: Will have all the :meth:`.create` parameters in it, as well as everything in
                the ``other_arguments`` argument to :func:`YosysNetlistBuild.__init__`.

        Return:
            True if everything went well.
        """
        return True

    def _get_synth_command(self) -> str:
        # The design is flattened so that the produced utilization report contains the
        # primitive counts for the whole design, and not just the top level.
        return f"{self.synth_command} -top {self.top} -flatten"

    def _get_yosys_script(
        self,
        workdir: Path,
        all_generics: dict[str, bool | float | StringGenericValue | BitVectorGenericValue],
        utilization_report_file: Path,
    ) -> str:
        top_library = self._get_top_level_module().library_name

        generic_arguments = " ".join(
            f"-g{name}={_get_ghdl_generic_value(value)}" for name, value in all_generics.items()
        )
        ghdl_command = (
            f"ghdl --std={self._vhdl_standard} --workdir={workdir} -P={workdir} "
            f"--work={top_library} {generic_arguments} {self.top}"
        )

        commands = [
            ghdl_command,
            self._get_synth_command(),
            f"tee -o {to_yosys_path(utilization_report_file)} stat",
        ]

        return "\n".join(commands) + "\n"

    def build(
        self,
        project_path: Path,
        output_path: Path | None = None,
        generics: dict[str, bool | float | StringGenericValue | BitVectorGenericValue]
        | None = None,
        **pre_and_post_build_parameters: Any,  # noqa: ANN401
    ) -> BuildResult:
        """
        Synthesize the design with Yosys.

        Arguments:
            project_path: A path containing the result of a call to :meth:`.create`.
            output_path: The utilization report, and any other artifacts, will be placed here.
                Will default to ``project_path`` if not set.
            generics: A dict with generics values (`dict(name: value)`). Use for run-time
                generics, i.e. values that can change between each build of this project.
                Compare to the create-time generics argument in :meth:`.__init__`.
                The generic value types follow the same rules as for :meth:`.__init__`.
            pre_and_post_build_parameters: Optional further arguments. Will not be used by
                tsfpga, but will instead be sent to

                * :func:`BaseModule.pre_build() <tsfpga.module.BaseModule.pre_build>`
                * :func:`YosysNetlistBuild.pre_build`
                * :func:`YosysNetlistBuild.post_build`

                along with further ``other_arguments`` supplied to :meth:`.__init__`.

                .. note::
                    This is a "kwargs" style argument. You can pass any number of named arguments.

        Return:
            Result object with build information.
        """
        workdir = self._get_ghdl_workdir(project_path=project_path)
        if not workdir.exists():
            raise ValueError(
                f'Project "{self.name}" does not exist in the specified location: {project_path}. '
                "Call 'create' before 'build'."
            )

        output_path = project_path if output_path is None else output_path
        create_directory(output_path, empty=False)

        print(f"Synthesizing Yosys netlist build {self.name} in {project_path}")

        all_generics = copy_and_combine_dicts(self.static_generics, generics)
        all_parameters = copy_and_combine_dicts(self.other_arguments, pre_and_post_build_parameters)
        all_parameters.update(
            project_path=project_path, output_path=output_path, generics=all_generics
        )

        # See 'create' for the rationale of doing this copy here as well.
        self.modules = deepcopy(self.modules)

        result = BuildResult(name=self.name, synthesis_run_name="synth")

        for module in self.modules:
            if not module.pre_build(project=self, **all_parameters):
                print(
                    f"ERROR: Module {module.name} pre-build hook returned False. Failing the build."
                )
                result.success = False
                return result

            # Make sure register packages are up to date.
            module.create_register_synthesis_files()

        if not self.pre_build(**all_parameters):
            print("ERROR: Project pre-build hook returned False. Failing the build.")
            result.success = False
            return result

        utilization_report_file = output_path / f"{self.name}_utilization.txt"
        script = self._get_yosys_script(
            workdir=workdir,
            all_generics=all_generics,
            utilization_report_file=utilization_report_file,
        )

        script_file = self.project_file(project_path=output_path)
        script_file.write_text(script)

        if not run_yosys(
            yosys_path=self._yosys_path,
            ghdl_plugin_path=self._ghdl_plugin_path,
            script_file=script_file,
            cwd=output_path,
            ghdl_prefix=self._ghdl_prefix,
        ):
            print(f'ERROR: Yosys synthesis failed for "{self.name}".')
            result.success = False
            return result

        result.synthesis_size = self._get_size(utilization_report_file=utilization_report_file)
        result.success = self._check_size(build_result=result)

        # Send the result object, along with everything else, to the post-build function.
        all_parameters.update(build_result=result)

        if not self.post_build(**all_parameters):
            print("ERROR: Project post-build hook returned False. Failing the build.")
            result.success = False

        return result

    def pre_build(
        self,
        **kwargs: Any,  # noqa: ANN401, ARG002
    ) -> bool:
        """
        Override this function in a subclass if you wish to do something useful with it.
        Will be called from :meth:`.build` right before the call to Yosys.

        Arguments:
            kwargs: Will have all the :meth:`.build` parameters in it. Including additional
                parameters from the user.

        Return:
            True if everything went well.
        """
        return True

    def post_build(
        self,
        **kwargs: Any,  # noqa: ANN401, ARG002
    ) -> bool:
        """
        Override this function in a subclass if you wish to do something useful with it.
        Will be called from :meth:`.build` right after the call to Yosys.

        .. Note::
            This default method does nothing. Shall be overridden by project that utilize
            this mechanism.

        Arguments:
            kwargs: Will have all the :meth:`.build` parameters in it. Including additional
                parameters from the user. Will also include ``build_result``.

        Return:
            True if everything went well.
        """
        return True

    def _get_size(self, utilization_report_file: Path) -> dict[str, int]:
        return YosysUtilizationParser.get_size(report=read_file(utilization_report_file))

    def _check_size(self, build_result: BuildResult) -> bool:
        success = True
        for build_result_checker in self.build_result_checkers:
            checker_result = build_result_checker.check(build_result)
            success = success and checker_result

        return success

    def open(
        self,
        project_path: Path,
    ) -> NoReturn:
        """
        Not implemented. A Yosys netlist build has no GUI to open.
        """
        raise NotImplementedError("Yosys netlist build can not be opened")

    def __str__(self) -> str:
        result = f"{self.name}\n"

        if self.defined_at is not None:
            result += f"Defined at: {self.defined_at.resolve()}\n"

        result += f"Type:       {self.__class__.__name__}\n"
        result += f"Top level:  {self.top}\n"

        generics = self._dict_to_string(self.static_generics) if self.static_generics else "-"
        result += f"Generics:   {generics}\n"

        if self.other_arguments:
            result += f"Arguments:  {self._dict_to_string(self.other_arguments)}\n"

        return result

    @staticmethod
    def _dict_to_string(data: dict[str, Any]) -> str:
        return ", ".join([f"{name}={value}" for name, value in data.items()])


class YosysXilinxNetlistBuild(YosysNetlistBuild):
    """
    Used for handling a Yosys netlist build that targets Xilinx primitives (LUTs, FDs,
    RAMBs, DSP48s, ...), using the Yosys ``synth_xilinx`` command.

    Since the produced utilization report uses the same resource naming convention as the
    Vivado utilization report, the checkers in :mod:`.vivado.build_result_checker` can be used
    directly to check e.g. the LUT or RAMB count of the design.
    """

    def __init__(
        self,
        family: str | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """
        Arguments:
            family: Optionally target a specific Xilinx device family (e.g. ``"xc7"``).
                See the Yosys ``synth_xilinx`` command documentation for valid values.
            kwargs: Further arguments accepted by :meth:`.YosysNetlistBuild.__init__`.
                Note that ``synth_command`` may not be set, since it is set by this class.
        """
        synth_command = "synth_xilinx"
        if family is not None:
            synth_command += f" -family {family}"

        super().__init__(synth_command=synth_command, **kwargs)


def _get_ghdl_generic_value(
    value: bool | float | StringGenericValue | BitVectorGenericValue,
) -> str:
    """
    Convert a generic value of a native Python type (or one of the tsfpga generic value
    wrapper classes) to a string suitable for the ``-g<name>=<value>`` argument of the
    ``ghdl-yosys-plugin`` ``ghdl`` command.
    """
    # Note that bool is a sub-class of int in Python, so check for bool must be first.
    if isinstance(value, bool):
        # The plugin does not recognize "1"/"0" as boolean literals, only "true"/"false".
        return "true" if value else "false"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        return str(value)

    if isinstance(value, BitVectorGenericValue):
        return value.value

    if isinstance(value, StringGenericValue):
        return value.value

    message = f'Unsupported type for generic. Got type="{type(value)}", value="{value}".'
    if isinstance(value, str):
        message += (
            " Please use either of the explicit types StringGenericValue or BitVectorGenericValue."
        )

    raise TypeError(message)


@contextmanager
def _suppress_stdout() -> Iterator[None]:
    """
    Suppress the (very chatty) printouts made by VUnit when creating a project.
    """
    with Path(os.devnull).open("w") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout
