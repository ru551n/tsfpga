# Standard libraries
from argparse import Namespace
from pathlib import Path
from shutil import which
import subprocess
from typing import Any, List, Optional

# Third party libraries
from vunit.ui.source import SourceFile
from vunit.ui import VUnit
from vunit.vhdl_standard import VHDLStandard
from vunit.ostools import Process

# First party libraries
from tsfpga.module import BaseModule
from tsfpga.module_list import ModuleList
from tsfpga.system_utils import create_directory
from tsfpga.vivado.build_result import BuildResult

# TODO: Result parsing (utilization, logic levels and static timing)
# TODO: Generics support
# TODO: Multiple libraries


class YosysNetlistBuild:
    def __init__(
        self,
        name: str,
        top: str,
        top_module: "BaseModule",
        modules: Optional["ModuleList"] = None,
        synth_command: Optional[str] = None,
        generics: Optional[dict[str, Any]] = None,
        ghdl_path: Optional[Path] = None,
        yosys_path: Optional[Path] = None,
        defined_at: Optional[Path] = None,
        vhdl_standard: VHDLStandard = VHDLStandard("2008"),
        **other_arguments: Any,
    ):
        self.name = name

        self.top_module = top_module
        self.modules = ModuleList() if modules is None else modules.copy()
        self.modules.append(top_module)

        if synth_command is not None:
            assert synth_command.startswith("synth"), "Must be Yosys synth command"
        self.synth_command = synth_command

        self.static_generics = {} if generics is None else generics.copy()
        self._ghdl_path = ghdl_path
        self._yosys_path = yosys_path
        self.defined_at = defined_at
        self.other_arguments = None if other_arguments is None else other_arguments.copy()

        self.top = top

        self.is_netlist_build = True
        self.analyze_synthesis_timing = True

        self._vhdl_standard = vhdl_standard

        self._vunit_proj = self._create_vunit_project(self.modules)

        # Order in which libraries are compiled, and hence the order
        # in which they need to be loaded into Yosys.
        self._library_compile_order = []

        self._implementation_subset = None

    def open(self):
        """
        Dummy since roject can't be opened.
        """
        raise RuntimeError("Yosys netlist project can't be opened")

    def __str__(self) -> str:
        result = f"{self.name}\n"

        if self.defined_at is not None:
            result += f"Defined at: {self.defined_at.resolve()}\n"

        result += f"Type:       {self.__class__.__name__}\n"
        result += f"Top level:  {self.top}\n"

        if self.static_generics:
            generics = self._dict_to_string(self.static_generics)
        else:
            generics = "-"
        result += f"Generics:   {generics}\n"

        if self.other_arguments:
            result += f"Arguments:  {self._dict_to_string(self.other_arguments)}\n"

        return result

    @staticmethod
    def _dict_to_string(data: dict[str, Any]) -> str:
        return ", ".join([f"{name}={value}" for name, value in data.items()])

    def _create_vunit_project(sel, modules: ModuleList) -> VUnit:

        dummy_args = Namespace()
        dummy_args.output_path = Path("out")
        dummy_args.log_level = "error"
        dummy_args.no_color = True
        dummy_args.clean = False

        vunit_proj = VUnit.from_args(args=dummy_args)

        for module in modules:
            vunit_library = vunit_proj.add_library(
                library_name=module.library_name, allow_duplicate=True
            )
            for hdl_file in module.get_synthesis_files():
                vunit_library.add_source_file(hdl_file.path)

        return vunit_proj

    def _get_ghdl_path(self) -> Path:
        if self._ghdl_path is not None:
            return self._ghdl_path.resolve()

        which_ghdl = which("ghdl")
        if which_ghdl is None:
            raise FileNotFoundError("Could not find ghdl on PATH")

        return Path(which_ghdl).resolve()

    def _get_yosys_path(self) -> Path:
        if self._yosys_path is not None:
            return self._yosys_path.resolve().as_posix()

        which_yosys = which("yosys")
        if which_yosys is None:
            raise FileNotFoundError("Could not find yosys on PATH")

        return Path(which_yosys).resolve().as_posix()

    def _get_top_file(self) -> Optional[SourceFile]:
        """
        Returns top level, assumes file is named the same as top level entity.
        Top level must be VHDL.
        """

        top_file_pattern = "*" + self.top + ".vhd"

        vhd_top_file = self._vunit_proj.get_source_file(
            top_file_pattern, library_name=self.top_module.library_name
        )

        return vhd_top_file

    def _get_required_synthesis_files(self) -> List[SourceFile]:
        """
        Create a list of of only the required files for the top level in the correct compile order.
        Assumes top level file has same name as the source file it is defined in.
        """

        if self._implementation_subset is None:
            top_file = self._get_top_file()
            self._implementation_subset = self._vunit_proj.get_implementation_subset([top_file])

            for file in reversed(self._implementation_subset):
                if file.library.name not in self._library_compile_order:
                    self._library_compile_order.insert(0, file.library.name)

        return self._implementation_subset

    def _get_synth_command(self) -> str:
        if self.synth_command is None:
            command = "synth"
        else:
            command = self.synth_command

        command += f" -top {self.top}"

        return command

    def _get_ghdl_standard_option(self) -> str:
        return "--std=" + self._vhdl_standard._standard[2:]

    def _ghdl_analyze_file(self, file: SourceFile, cwd: Path) -> bool:
        file_path = Path(file.name).resolve().absolute().as_posix()

        cmd = [
            "ghdl",
            "-a",
            self._get_ghdl_standard_option(),
            f"--workdir={cwd}",
            f"-P={cwd}",
            f"--work={file.library.name}",
            file_path,
        ]

        result = subprocess.run(cmd, cwd=cwd)

        return result.returncode == 0

    def _get_vhdl_files(self) -> List[SourceFile]:
        files = self._get_required_synthesis_files()
        return [file for file in files if file.name.endswith(".vhd")]

    def _get_verilog_files(self) -> List[SourceFile]:
        files = self._get_required_synthesis_files()
        return [file for file in files if file.name.endswith(".v")]

    def _ghdl_analyze(self, output_path: Path) -> bool:
        success = False

        for file in self._get_vhdl_files():
            success = self._ghdl_analyze_file(file, output_path)
            if not success:
                return success

        return success

    def _create_script(self, ghdl_output_path: Path) -> str:

        script = []

        # Load GHDL top level library
        top_library = self._get_top_file().library.name
        script.append(
            f"ghdl {self._get_ghdl_standard_option()} --work={top_library} --workdir={ghdl_output_path} -P={ghdl_output_path}"
        )

        for file in self._get_verilog_files():
            file_path = Path(file.name).resolve().absolute().as_posix()

            script.append(f"read_verilog {file_path}")

        # Set synthesis command
        script.append(self._get_synth_command())

        # Create script command
        script_str = "; ".join(script)

        return script_str

    def _run_yosys(self, output_path: Path, ghdl_output_path: Path) -> BuildResult:

        script = self._create_script(ghdl_output_path)

        cmd = [self._get_yosys_path(), "-m", "ghdl", "-p", script]

        result = BuildResult(self.name)

        try:
            Process(args=cmd, cwd=output_path).consume_output()
        except Process.NonZeroExitCode:
            result.success = False
        else:
            result.success = True

        return result

    def build(self, project_path: Path, output_path: Path, **kwargs) -> bool:

        ghdl_output_path = output_path / "ghdl"
        create_directory(ghdl_output_path, empty=True)

        success = self._ghdl_analyze(ghdl_output_path)
        if not success:
            raise RuntimeError("GHDL analysis failed")

        success = self._run_yosys(output_path, ghdl_output_path)

        return success
