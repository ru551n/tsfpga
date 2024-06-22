

import pytest
from tsfpga.module_list import ModuleList
from tsfpga.yosys.project import YosysNetlistBuild
from vunit.vhdl_standard import VHDLStandard



def test_no_modules_doesnt_find_top_level():
    
    modules = ModuleList()
    proj = YosysNetlistBuild(name="foo", top="foo_top", modules=modules, lut_arch=6)
    
    files = None
    with pytest.raises(ValueError) as exception_info:
        files = proj._get_required_synthesis_files()
        
    assert str(exception_info.value) == "Could not determine top level, multiple or no files containing top level found"
    assert files == None
    
def test_create_script():

    for vhdl_standard in ["1993", "2002", "2008", "2019"]:
        for lut_arch in [None, 4, 6]:
            for synth_command in [None, "synth_xilinx"]:
                proj = YosysNetlistBuild(name="hest", modules=ModuleList(), top="hest_top", lut_arch=lut_arch, synth_command=synth_command, vhdl_standard=VHDLStandard(vhdl_standard))
                script = proj._create_script()
                
                expected_script = f"ghdl --std={vhdl_standard[2:]} hest_top;"
                
                if synth_command:
                    expected_script += synth_command + ";"
                else:
                    if lut_arch is None:
                        expected_script += f"synth;"
                    else:
                        expected_script += f"synth -lut {lut_arch};"
                        
                assert script == expected_script