from argparse import Namespace
from multiprocessing import Process
from pathlib import Path
from shutil import which
import subprocess
from typing import Any, List, Optional

from tsfpga.module_list import ModuleList
from vunit.source_file import SourceFile
from vunit.ui import VUnit
from vunit.vhdl_standard import VHDLStandard

from tsfpga.hdl_file import HdlFile

# TODO: Verilog support
# TODO: Result parsing (utilization, logic levels and static timing)
# TODO: Generics support


class YosysNetlistBuild:
    def __init__(
        self,
        name: str,
        modules: "ModuleList",
        top: str,
        synth_command: Optional[str] = None,
        generics: Optional[dict[str, Any]] = None,
        ghdl_path: Optional[Path] = None,
        yosys_path: Optional[Path] = None,
        vhdl_standard: VHDLStandard = VHDLStandard("2008"),
    ):

        self.name = name
        self.modules = modules.copy()

        if synth_command is not None:
            assert synth_command.startswith("synth"), "Must be Yosys synth command"
        self.synth_command = synth_command

        self.static_generics = {} if generics is None else generics.copy()
        self._ghdl_path = ghdl_path
        self._yosys_path = yosys_path

        self.top = name + "_top" if top is None else top

        self.is_netlist_build = True

        self._vhdl_standard = vhdl_standard

        self._vunit_proj = self._create_vunit_project(modules)

        # Libraries to be used when loading via GHDL plugin in Yosys
        self._libraries = []
        for module in modules:
            if module.get_synthesis_files():
                self._libraries.append(module.name)

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
                assert hdl_file.type == HdlFile.Type.VHDL, "Only VHDL currently supported"
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
            return self._yosys_path.resolve()

        which_yosys = which("yosys")
        if which_yosys is None:
            raise FileNotFoundError("Could not find yosys on PATH")

        return Path(which_yosys).resolve()

    def _run_process(self, cmd: List[str], cwd: Path):
        # try:
        #     Process(args=cmd, cwd=cwd).consume_output()
        # except:
        #     return False
        subprocess.run(cmd, cwd=cwd)
        return True

    def _get_top_file(self) -> Optional[SourceFile]:
        """
        Returns top level, assumes file is named the same as top level entity

        Args:
            vunit_proj (VUnit): _description_

        Returns:
            Optional[SourceFile]: File which contains the top level
        """
        top_file_pattern = "*" + self.top + ".vhd"

        try:
            vhd_top_file = self._vunit_proj.get_source_file(top_file_pattern)
        except ValueError:
            vhd_top_file = None

        if vhd_top_file is not None:
            return vhd_top_file

        return None

    def _get_required_synthesis_files(self) -> List[SourceFile]:
        """
        Create a list of of only the required files for the top level.
        Assumes top level file has same name as the source file it is defined in.
        """
        top_file = self._get_top_file()

        if top_file is None:
            raise ValueError(
                "Could not determine top level, multiple or no files containing top level found"
            )

        implementation_subset = self._vunit_proj.get_implementation_subset([top_file])
        return self._vunit_proj.get_compile_order(implementation_subset)

    def _get_synth_command(self) -> str:
        if self.synth_command is None:
            command = f"synth"
        else:
            command = self.synth_command

        command += f" -top {self.top}"

        return command

    def _get_ghdl_standard_option(self) -> str:
        return "--std=" + self._vhdl_standard._standard[2:]

    def _ghdl_analyze_file(self, file: SourceFile, output_path: Path) -> bool:

        file_path = Path(file.name).absolute()

        cmd = [
            "ghdl",
            "-a",
            self._get_ghdl_standard_option(),
            f"--work={file.library.name}",
            file_path,
        ]

        return self._run_process(cmd, output_path)

    def _ghdl_analyze(self, output_path: Path) -> bool:

        success = False

        # TODO: This can be optimized to reduce the number of GHDL calls, further reducing runtime.
        for file in self._get_required_synthesis_files():
            if file.name.endswith(".vhd"):
                success = self._ghdl_analyze_file(file, output_path)
                if not success:
                    return success

        return success

    def _create_script(self) -> str:

        script = []

        # Load previously analyzed VHDL design libraries
        for library in self._libraries:
            script.append(f"ghdl {self._get_ghdl_standard_option()} --work={library}")

        # TODO: Load verilog files here!

        # Set synthesis command
        script.append(self._get_synth_command())

        # Static timing analysys
        script.append("sta")

        # Create script command
        script_str = "; ".join(script)

        return script_str

    def _run_yosys(self, output_path: Path) -> bool:

        script = self._create_script()

        cmd = [self._get_yosys_path(), "-m", "ghdl", "-p", script]

        success = self._run_process(cmd, output_path)
        return success

    def build(self, output_path: Path) -> bool:

        success = self._ghdl_analyze(output_path)
        if not success:
            return False

        success = self._run_yosys(output_path=output_path)

        return success
