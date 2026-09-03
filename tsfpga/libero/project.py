# --------------------------------------------------------------------------------------------------
# Copyright (c) Lukas Vik. All rights reserved.
#
# This file is part of the tsfpga project, a project platform for modern FPGA development.
# https://tsfpga.com
# https://github.com/tsfpga/tsfpga
# --------------------------------------------------------------------------------------------------

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tsfpga.build_step_tcl_hook import BuildStepTclHook
from tsfpga.constraint import Constraint
from tsfpga.system_utils import create_file
from tsfpga.vivado.build_result import BuildResult
from tsfpga.vivado.project import copy_and_combine_dicts

from .common import run_libero_gui, run_libero_tcl
from .mss import MssConfiguration
from .tcl import LiberoTcl

if TYPE_CHECKING:
    from tsfpga.module_list import ModuleList
    from tsfpga.vivado.generics import BitVectorGenericValue, StringGenericValue


class LiberoProject:
    """
    Used for handling a Microchip Libero SoC HDL project.

    Follows the same hook-based extension model as :class:`.VivadoProject`
    (:meth:`.pre_create`, :meth:`.pre_build`, :meth:`.post_build`), and implements the same
    public interface (``name``, ``is_netlist_build``, :meth:`.create`, :meth:`.build`,
    :meth:`.open`, :meth:`.project_file`, ``__str__``) so that it can be used interchangeably
    with :class:`.VivadoProject` in a :class:`.BuildProjectList`.

    .. warning::
        This class has been developed against the Libero SoC Tcl command reference documentation
        only. It has **not** been verified against a real Libero SoC installation.
        Notable limitations compared to :class:`.VivadoProject`:

        * Generics/parameters are set right before synthesis using
          ``set_option -hdl_param -set <name> <value>``, and only VHDL literal syntax is
          supported. See :meth:`.LiberoTcl._add_generics`.
        * Both ``.sdc`` timing constraints and ``.pdc`` pin/floorplanning constraints are
          supported. Scoped constraints and a non-default processing order are not supported.
          See :meth:`.LiberoTcl._add_constraints`.
        * IP cores (the Libero "vault"/SmartDesign ecosystem) can be added using the same
          :class:`.IpCoreFile` mechanism as for Vivado, since it is tool-agnostic.
          See :meth:`.LiberoTcl._add_ip_cores`.
        * A Microcontroller Subsystem (MSS) component can be generated and imported using
          :class:`.MssConfiguration`. Confirmed for PolarFire SoC only.
          See :meth:`.LiberoTcl._add_mss_components`.
        * :attr:`.BuildResult.synthesis_size` / ``implementation_size`` are not populated, since
          this requires a resource-utilization report parser that has not yet been implemented.
          The exact machine-parsable format of the Libero SoC "Compile Report" could not be
          confirmed from documentation alone.
    """

    def __init__(  # noqa: PLR0913
        self,
        name: str,
        modules: ModuleList,
        family: str,
        die: str,
        package: str,
        top: str | None = None,
        speed: str = "-1",
        die_voltage: str = "1.0",
        hdl: str = "VHDL",
        generics: dict[str, bool | float | StringGenericValue | BitVectorGenericValue]
        | None = None,
        constraints: list[Constraint] | None = None,
        tcl_sources: list[Path] | None = None,
        mss_configurations: list[MssConfiguration] | None = None,
        mss_configurator_path: Path | None = None,
        build_step_hooks: list[BuildStepTclHook] | None = None,
        libero_path: Path | None = None,
        defined_at: Path | None = None,
        **other_arguments: Any,  # noqa: ANN401
    ) -> None:
        """
        Class constructor. Performs a shallow copy of the mutable arguments, so that the user
        can e.g. append items to their list after creating an object.

        Arguments:
            name: Project name.
            modules: Modules that shall be included in the project.
            family: Device family identification, e.g. ``"PolarFire"``.
            die: Device die identification, e.g. ``"MPF300TS_ES"``.
            package: Device package identification, e.g. ``"FCG1152"``.
            top: Name of top level entity.
                If left out, the top level name will be inferred from the ``name``.
            speed: Device speed grade.
            die_voltage: Device die voltage.
            hdl: Target language. Either ``"VHDL"`` or ``"VERILOG"``.
            generics: A dict with generics values (name: value). These are static, i.e. they
                will be used for every build of this project. Can be overridden/complemented
                with the ``generics`` argument to :meth:`.build`.

                .. warning::
                    See class docstring for limitations.
            constraints: Constraints that will be applied to the project.
                Both ``.sdc`` and ``.pdc`` files are supported. See class docstring.
            tcl_sources: A list of TCL files. Use for e.g. project settings.
            mss_configurations: A list of Microcontroller Subsystem (MSS) configurations that
                shall be generated and imported into the project.

                .. warning::
                    See class docstring for limitations. Confirmed for PolarFire SoC only.
            mss_configurator_path: A path to the standalone MSS Configurator executable.
                If omitted, the default location from the system PATH will be used
                (``pfsoc_mss`` for PolarFire SoC).
            build_step_hooks: Build step hooks that will be applied to the project.
                Since Libero SoC has no native per-step Tcl hook property, these are emulated by
                ``source``-ing the hook file immediately before/after the relevant ``run_tool``
                call. Use hook step names ``"<TOOL NAME>.PRE"``/``"<TOOL NAME>.POST"``,
                e.g. ``"SYNTHESIZE.PRE"``.
            libero_path: A path to the Libero SoC executable.
                If omitted, the default location from the system PATH will be used.
            defined_at: Optional path to the file where you defined this project.
                To get a useful ``build_fpga.py --list`` message. Is useful when you have many
                projects set up.
            other_arguments: Optional further arguments. Will not be used by tsfpga, but will
                instead be passed on to

                * :func:`BaseModule.get_synthesis_files()
                  <tsfpga.module.BaseModule.get_synthesis_files>`
                * :func:`BaseModule.get_scoped_constraints()
                  <tsfpga.module.BaseModule.get_scoped_constraints>`
                * :func:`LiberoProject.pre_create`
                * :func:`BaseModule.pre_build() <tsfpga.module.BaseModule.pre_build>`
                * :func:`LiberoProject.pre_build`
                * :func:`LiberoProject.post_build`

                along with further arguments supplied at build-time to :meth:`.create` and
                :meth:`.build`.

                .. note::
                    This is a "kwargs" style argument. You can pass any number of named arguments.
        """
        self.name = name
        self.modules = modules.copy()
        self.family = family
        self.die = die
        self.package = package
        self.speed = speed
        self.die_voltage = die_voltage
        self.hdl = hdl
        self.static_generics = {} if generics is None else generics.copy()
        self.constraints = [] if constraints is None else constraints.copy()
        self.tcl_sources = [] if tcl_sources is None else tcl_sources.copy()
        self.mss_configurations = [] if mss_configurations is None else mss_configurations.copy()
        self._mss_configurator_path = mss_configurator_path
        self.build_step_hooks = [] if build_step_hooks is None else build_step_hooks.copy()
        self._libero_path = libero_path
        self.defined_at = defined_at
        self.other_arguments = None if other_arguments is None else other_arguments.copy()

        # Will be set by subclass when applicable. Present so that this class can be used
        # interchangeably with 'VivadoProject' in a 'BuildProjectList'/'get_build_projects()'.
        self.is_netlist_build = False

        self.top = name + "_top" if top is None else top

        self.tcl = LiberoTcl(name=self.name)

        for constraint in self.constraints:
            if not isinstance(constraint, Constraint):
                raise TypeError(f'Got bad type for "constraints" element: {constraint}')

        for tcl_source in self.tcl_sources:
            if not isinstance(tcl_source, Path):
                raise TypeError(f'Got bad type for "tcl_sources" element: {tcl_source}')

        for mss_configuration in self.mss_configurations:
            if not isinstance(mss_configuration, MssConfiguration):
                raise TypeError(
                    f'Got bad type for "mss_configurations" element: {mss_configuration}'
                )

        for build_step_hook in self.build_step_hooks:
            if not isinstance(build_step_hook, BuildStepTclHook):
                raise TypeError(f'Got bad type for "build_step_hooks" element: {build_step_hook}')

    def project_file(self, project_path: Path) -> Path:
        """
        Arguments:
            project_path: A path containing a Libero SoC project.

        Return:
            The project file of this project, in the given folder.
        """
        return project_path / f"{self.name}.prjx"

    def _create_tcl(self, project_path: Path, all_arguments: dict[str, Any]) -> Path:
        """
        Make a TCL file that creates a Libero SoC project.
        """
        project_file = self.project_file(project_path=project_path)
        if project_file.exists():
            raise ValueError(f'Project "{self.name}" already exists: {project_file}')
        project_path.mkdir(parents=True, exist_ok=True)

        create_libero_project_tcl = project_path / "create_libero_project.tcl"
        tcl = self.tcl.create(
            project_folder=project_path,
            modules=self.modules,
            family=self.family,
            die=self.die,
            package=self.package,
            top=self.top,
            speed=self.speed,
            die_voltage=self.die_voltage,
            hdl=self.hdl,
            constraints=self.constraints,
            tcl_sources=self.tcl_sources,
            mss_configurations=self.mss_configurations,
            mss_configurator_path=self._mss_configurator_path,
            other_arguments=all_arguments,
        )
        create_file(create_libero_project_tcl, tcl)

        return create_libero_project_tcl

    def create(
        self,
        project_path: Path,
        ip_cache_path: Path | None = None,  # noqa: ARG002
        **other_arguments: Any,  # noqa: ANN401
    ) -> bool:
        """
        Create a Libero SoC project.

        Arguments:
            project_path: Path where the project shall be placed.
            ip_cache_path: Not used. Present for interface compatibility with
                :meth:`.VivadoProject.create`.
            other_arguments: Optional further arguments. Will not be used by tsfpga, but will
                instead be sent to

                * :func:`BaseModule.get_synthesis_files()
                  <tsfpga.module.BaseModule.get_synthesis_files>`
                * :func:`BaseModule.get_scoped_constraints()
                  <tsfpga.module.BaseModule.get_scoped_constraints>`
                * :func:`LiberoProject.pre_create`

                along with further ``other_arguments`` supplied to :meth:`.__init__`.

                .. note::
                    This is a "kwargs" style argument. You can pass any number of named arguments.

        Return:
            True if everything went well.
        """
        print(f"Creating Libero SoC project in {project_path}")

        # The pre-create hook might have side effects. E.g. change some register constants.
        # So we make a deep copy of the module list before the hook is called.
        self.modules = deepcopy(self.modules)

        all_arguments = copy_and_combine_dicts(self.other_arguments, other_arguments)

        if not self.pre_create(project_path=project_path, **all_arguments):
            print("ERROR: Project pre-create hook returned False. Failing the build.")
            return False

        create_libero_project_tcl = self._create_tcl(
            project_path=project_path, all_arguments=all_arguments
        )
        return run_libero_tcl(self._libero_path, create_libero_project_tcl)

    def pre_create(
        self,
        **kwargs: Any,  # noqa: ANN401, ARG002
    ) -> bool:
        """
        Override this function in a subclass if you wish to do something useful with it.
        Will be called from :meth:`.create` right before the call to Libero SoC.

        .. Note::
            This default method does nothing. Shall be overridden by project that utilize
            this mechanism.

        Arguments:
            kwargs: Will have all the :meth:`.create` parameters in it, as well as everything in
                the ``other_arguments`` argument to :func:`LiberoProject.__init__`.

        Return:
            True if everything went well.
        """
        return True

    def _build_tcl(
        self,
        project_path: Path,
        output_path: Path | None,
        all_generics: dict[str, bool | float | StringGenericValue | BitVectorGenericValue],
        synth_only: bool,
    ) -> Path:
        """
        Make a TCL file that builds a Libero SoC project.
        """
        project_file = self.project_file(project_path=project_path)
        if not project_file.exists():
            raise ValueError(
                f'Project "{self.name}" does not exist in the specified location: {project_file}'
            )

        build_libero_project_tcl = project_path / "build_libero_project.tcl"
        tcl = self.tcl.build(
            project_file=project_file,
            top=self.top,
            output_path=output_path,
            build_step_hooks=self.build_step_hooks,
            generics=all_generics,
            hdl=self.hdl,
            synth_only=synth_only,
        )
        create_file(build_libero_project_tcl, tcl)

        return build_libero_project_tcl

    def pre_build(
        self,
        **kwargs: Any,  # noqa: ANN401, ARG002
    ) -> bool:
        """
        Override this function in a subclass if you wish to do something useful with it.
        Will be called from :meth:`.build` right before the call to Libero SoC.

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
        Will be called from :meth:`.build` right after the call to Libero SoC.

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

    def build(
        self,
        project_path: Path,
        output_path: Path | None = None,
        generics: dict[str, bool | float | StringGenericValue | BitVectorGenericValue]
        | None = None,
        synth_only: bool = False,
        **pre_and_post_build_parameters: Any,  # noqa: ANN401
    ) -> BuildResult:
        """
        Build a Libero SoC project.

        Arguments:
            project_path: A path containing a Libero SoC project.
            output_path: Results (bitstream, ...) will be placed here.
            generics: A dict with generics values (`dict(name: value)`). Use for run-time
                generics, i.e. values that can change between each build of this project.
                Compare to the create-time generics argument in :meth:`.__init__`.
                The generic value types follow the same rules as for :meth:`.__init__`.
            synth_only: Run synthesis and then stop.
            pre_and_post_build_parameters: Optional further arguments. Will not be used by
                tsfpga, but will instead be sent to

                * :func:`BaseModule.pre_build() <tsfpga.module.BaseModule.pre_build>`
                * :func:`LiberoProject.pre_build`
                * :func:`LiberoProject.post_build`

                along with further ``other_arguments`` supplied to :meth:`.__init__`.

                .. note::
                    This is a "kwargs" style argument. You can pass any number of named arguments.

        Return:
            Result object with build information.
        """
        synth_only = synth_only or self.is_netlist_build

        if synth_only:
            print(f"Synthesizing Libero SoC project in {project_path}")
        else:
            if output_path is None:
                raise ValueError("Must specify 'output_path' when doing an implementation build.")

            print(
                f"Building Libero SoC project in {project_path}, placing artifacts in {output_path}"
            )

        # Combine to all available generics. Prefer run-time values over static.
        all_generics = copy_and_combine_dicts(self.static_generics, generics)

        all_parameters = copy_and_combine_dicts(self.other_arguments, pre_and_post_build_parameters)
        all_parameters.update(
            project_path=project_path,
            output_path=output_path,
            generics=all_generics,
            synth_only=synth_only,
        )

        # See 'VivadoProject.build' for the rationale of doing this copy here as well as
        # in 'create()'.
        self.modules = deepcopy(self.modules)

        result = BuildResult(name=self.name, synthesis_run_name="SYNTHESIZE")

        for module in self.modules:
            if not module.pre_build(project=self, **all_parameters):
                print(
                    f"ERROR: Module {module.name} pre-build hook returned False. Failing the build."
                )
                result.success = False
                return result

            # Make sure register packages are up to date
            module.create_register_synthesis_files()

        if not self.pre_build(**all_parameters):
            print("ERROR: Project pre-build hook returned False. Failing the build.")
            result.success = False
            return result

        build_libero_project_tcl = self._build_tcl(
            project_path=project_path,
            output_path=output_path,
            all_generics=all_generics,
            synth_only=synth_only,
        )

        if not run_libero_tcl(self._libero_path, build_libero_project_tcl):
            result.success = False
            return result

        if not synth_only:
            result.implementation_run_name = "PLACEROUTE"

        # NOTE: Resource utilization and timing figures are not yet available.
        # 'result.synthesis_size'/'implementation_size' will remain 'None' until a Libero SoC
        # report parser has been implemented. See class docstring.

        # Send the result object, along with everything else, to the post-build function
        all_parameters.update(build_result=result)

        if not self.post_build(**all_parameters):
            print("ERROR: Project post-build hook returned False. Failing the build.")
            result.success = False

        return result

    def open(self, project_path: Path) -> bool:
        """
        Open the project in the Libero SoC GUI.

        Arguments:
            project_path: A path containing a Libero SoC project.

        Return:
            True if everything went well.
        """
        return run_libero_gui(self._libero_path, self.project_file(project_path))

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
