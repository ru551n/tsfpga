from argparse import Namespace
from multiprocessing import Process
from pathlib import Path
from shutil import which
from typing import Any, List, Optional

from tsfpga.module_list import ModuleList
from vunit.source_file import SourceFile
from vunit.ui import VUnit
from vunit.vhdl_standard import VHDLStandard

# TODO: Verilog support
# TODO: Result parsing (both for logic levels and )
# TODO

def run_commands(commands: List[str], cwd: Path):
    cmd = ""
    for command in commands:
        cmd += f"{command};"
    
    try:
        Process(args=cmd, cwd=cwd, shell=True).consume_output()
    except Process.NonZeroExitCode:
        return False
    return True


class YosysNetlistBuild:
    def __init__(
        self,
        name: str,
        modules: "ModuleList",
        top: str,
        lut_arch: Optional[int] = None,
        synth_command: Optional[str] = None,
        generics: Optional[dict[str, Any]] = None,
        ghdl_path: Optional[Path] = None,
        yosys_path: Optional[Path] = None,
        vhdl_standard: VHDLStandard = VHDLStandard("2008")
    ):
    
        self.name = name
        self.modules = modules.copy()
        self.lut_arch = lut_arch
        self.synth_command = synth_command
        self.static_generics = {} if generics is None else generics.copy()
        self._ghdl_path = ghdl_path
        self._yosys_path = yosys_path
        
        self.top = name + "_top" if top is None else top
        
        self.is_netlist_build = True
        
        self._vhdl_standard = vhdl_standard
        
        self._vunit_proj = self._create_vunit_project(modules)
        
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
            return self._yosys_path.resolve()
    
        which_ghdl = which("yosys")
        if which_ghdl is None:
            raise FileNotFoundError("Could not find yosys on PATH")
    
        return Path(which_ghdl).resolve()
    
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
            raise ValueError("Could not determine top level, multiple or no files containing top level found")
        
        implementation_subset = self._vunit_proj.get_implementation_subset([top_file])
        return self._vunit_proj.get_compile_order(implementation_subset)
            
    def _get_synth_command(self):
        if self.synth_command is None:
            command = "synth"
            if self.lut_arch is not None:
                command += f" -lut {self.lut_arch}"
        else:
            command = self.synth_command
            
        return command
    
    def _get_ghdl_standard_option(self):
        return "--std=" + self._vhdl_standard._standard[2:]
    
    def _ghdl_analyze_file(self, file : SourceFile, output_path : Path) -> bool:
        
        cmd = ['ghdl','-a',self._get_ghdl_standard_option(), file.name]
        
        assert file.is_vhdl, "Only VHDL currently supported"
        
        try:
            Process(args=cmd, cwd=output_path).consume_output()
        except Process.NonZeroExitCode:
            return False
        return True
    
    def _ghdl_analyze(self, output_path : Path) -> bool:
        
        for file in self._get_required_synthesis_files():
            success = self._ghdl_analyze_file(file, output_path)
            if not success:
                return success
            
        return success
        
    def _create_script(self) -> str:
        
        script = []
        
        # Load previously analyzed VHDL design
        script.append(f"ghdl " + self._get_ghdl_standard_option() + f" {self.top}")
        
        # Set synthesis command
        script.append(self._get_synth_command())
        
        script_str = ""
        for cmd in script:
            script_str += cmd + ";"
            
        return script_str
    
    def _run_script(self, script : str):
        pass