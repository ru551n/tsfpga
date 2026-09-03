# --------------------------------------------------------------------------------------------------
# Copyright (c) Lukas Vik. All rights reserved.
#
# This file is part of the tsfpga project, a project platform for modern FPGA development.
# https://tsfpga.com
# https://github.com/tsfpga/tsfpga
# --------------------------------------------------------------------------------------------------

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tsfpga.build_step_tcl_hook import BuildStepTclHook
from tsfpga.constraint import Constraint
from tsfpga.libero.tcl import LiberoTcl
from tsfpga.module import BaseModule
from tsfpga.module_list import ModuleList
from tsfpga.vivado.common import to_tcl_path
from tsfpga.vivado.generics import BitVectorGenericValue, StringGenericValue


def _get_tcl(**kwargs):
    return LiberoTcl(name="name").create(
        project_folder=Path("project"),
        modules=ModuleList(),
        family="PolarFire",
        die="MPF300TS_ES",
        package="FCG1152",
        top="top",
        **kwargs,
    )


def test_create_contains_new_project_and_set_root_and_save_project():
    tcl = _get_tcl()
    assert (
        "new_project "
        f"-location {{{to_tcl_path(Path('project'))}}} "
        "-name {name} "
        "-hdl {VHDL} "
        "-family {PolarFire} "
        "-die {MPF300TS_ES} "
        "-package {FCG1152} "
        "-speed {-1} "
        "-die_voltage {1.0}\n"
    ) in tcl
    assert "set_root -module {top::work}" in tcl
    assert tcl.rstrip().endswith("save_project")


def test_module_source_files_are_added():
    module = MagicMock(spec=BaseModule)
    hdl_file = MagicMock()
    hdl_file.path = Path("apa.vhd")
    module.get_synthesis_files.return_value = [hdl_file]

    modules = ModuleList()
    modules.append(module)

    tcl = LiberoTcl(name="name").create(
        project_folder=Path("project"),
        modules=modules,
        family="PolarFire",
        die="MPF300TS_ES",
        package="FCG1152",
        top="top",
    )
    assert f"import_files \\\n-hdl_source {{{to_tcl_path(Path('apa.vhd'))}}}" in tcl
    module.get_synthesis_files.assert_called_once_with()


def test_no_module_source_files_gives_no_import_files_hdl_source():
    tcl = _get_tcl()
    assert "-hdl_source" not in tcl


def test_tcl_sources_are_sourced():
    tcl = _get_tcl(tcl_sources=[Path("hest.tcl"), Path("zebra.tcl")])
    assert f"source -notrace {{{to_tcl_path(Path('hest.tcl'))}}}" in tcl
    assert f"source -notrace {{{to_tcl_path(Path('zebra.tcl'))}}}" in tcl


def test_constraints():
    constraints = [Constraint(file=Path("apa.sdc"))]
    tcl = _get_tcl(constraints=constraints)
    constraint_file = to_tcl_path(Path("apa.sdc"))

    assert f"import_files -sdc {{{constraint_file}}}" in tcl
    assert (
        f"organize_tool_files -tool {{SYNTHESIZE}} -file {{{constraint_file}}} "
        "-module {top::work}" in tcl
    )
    assert (
        f"organize_tool_files -tool {{PLACEROUTE}} -file {{{constraint_file}}} "
        "-module {top::work}" in tcl
    )
    assert (
        f"organize_tool_files -tool {{VERIFYTIMING}} -file {{{constraint_file}}} "
        "-module {top::work}" in tcl
    )


def test_constraint_only_used_in_synthesis():
    constraints = [Constraint(file=Path("apa.sdc"), used_in_implementation=False)]
    tcl = _get_tcl(constraints=constraints)

    assert "organize_tool_files -tool {SYNTHESIZE}" in tcl
    assert "organize_tool_files -tool {PLACEROUTE}" not in tcl
    assert "organize_tool_files -tool {VERIFYTIMING}" not in tcl


def test_no_constraints_gives_no_import_files_sdc():
    assert "import_files -sdc" not in _get_tcl()


def test_io_pdc_constraint():
    constraints = [Constraint(file=Path("apa_io.pdc"))]
    tcl = _get_tcl(constraints=constraints)
    constraint_file = to_tcl_path(Path("apa_io.pdc"))

    assert f"import_files -io_pdc {{{constraint_file}}}" in tcl
    assert (
        f"organize_tool_files -tool {{PLACEROUTE}} -file {{{constraint_file}}} "
        "-module {top::work}" in tcl
    )
    assert "organize_tool_files -tool {SYNTHESIZE}" not in tcl
    assert "organize_tool_files -tool {VERIFYTIMING}" not in tcl


def test_fp_pdc_constraint_is_guessed_from_file_name():
    constraints = [Constraint(file=Path("apa_fp.pdc"))]
    tcl = _get_tcl(constraints=constraints)
    constraint_file = to_tcl_path(Path("apa_fp.pdc"))

    assert f"import_files -fp_pdc {{{constraint_file}}}" in tcl


def test_pdc_constraint_not_used_in_implementation_is_not_organized():
    constraints = [Constraint(file=Path("apa_io.pdc"), used_in_implementation=False)]
    tcl = _get_tcl(constraints=constraints)

    assert "import_files -io_pdc" in tcl
    assert "organize_tool_files" not in tcl


def test_scoped_constraint_raises_not_implemented_error():
    constraints = [Constraint(file=Path("apa.sdc"), scoped_constraint=True)]
    with pytest.raises(NotImplementedError):
        _get_tcl(constraints=constraints)


def test_constraint_non_default_processing_order_raises_not_implemented_error():
    constraints = [Constraint(file=Path("apa.sdc"), processing_order="early")]
    with pytest.raises(NotImplementedError):
        _get_tcl(constraints=constraints)


def test_non_sdc_or_pdc_constraint_raises_not_implemented_error():
    constraints = [Constraint(file=Path("apa.xdc"))]
    with pytest.raises(NotImplementedError):
        _get_tcl(constraints=constraints)


def _get_build_tcl(**kwargs):
    return LiberoTcl(name="name").build(
        project_file=Path("project/name.prjx"), top="top", output_path=Path("output"), **kwargs
    )


def test_build_synth_only_does_not_run_implementation_steps():
    tcl = _get_build_tcl(synth_only=True)
    assert "run_tool -name {SYNTHESIZE}" in tcl
    assert "run_tool -name {PLACEROUTE}" not in tcl
    assert "export_bitstream_file" not in tcl
    assert tcl.rstrip().endswith("save_project")


def test_build_generics_are_set_before_synthesis():
    tcl = _get_build_tcl(
        generics={
            "apa": 3,
            "hest": True,
            "zebra": StringGenericValue("foo"),
            "zebra_two": BitVectorGenericValue("1010"),
        },
        synth_only=True,
    )
    generics_idx = tcl.index("set_option -hdl_param -set apa 3")
    synth_idx = tcl.index("run_tool -name {SYNTHESIZE}")
    assert generics_idx < synth_idx

    assert "set_option -hdl_param -set hest TRUE" in tcl
    assert 'set_option -hdl_param -set zebra "foo"' in tcl
    assert 'set_option -hdl_param -set zebra_two "1010"' in tcl


def test_no_generics_gives_no_set_option_hdl_param():
    assert "set_option -hdl_param" not in _get_build_tcl(generics={}, synth_only=True)
    assert "set_option -hdl_param" not in _get_build_tcl(generics=None, synth_only=True)


def test_build_generics_with_verilog_raises_not_implemented_error():
    with pytest.raises(NotImplementedError):
        _get_build_tcl(generics={"apa": 3}, hdl="VERILOG", synth_only=True)


def test_build_full_run_includes_all_steps_and_export():
    tcl = _get_build_tcl(synth_only=False)
    for name in (
        "SYNTHESIZE",
        "PLACEROUTE",
        "VERIFYTIMING",
        "VERIFYPOWER",
        "GENERATEPROGRAMMINGDATA",
        "GENERATEPROGRAMMINGFILE",
    ):
        assert f"run_tool -name {{{name}}}" in tcl
    export_dir = to_tcl_path(Path("output"))
    assert f"export_bitstream_file -file_name {{top}} -export_dir {{{export_dir}}}" in tcl


def test_build_without_output_path_raises_exception_unless_synth_only():
    LiberoTcl(name="name").build(
        project_file=Path("project/name.prjx"), top="top", output_path=None, synth_only=True
    )

    with pytest.raises(ValueError) as exception_info:
        LiberoTcl(name="name").build(
            project_file=Path("project/name.prjx"), top="top", output_path=None, synth_only=False
        )
    assert str(exception_info.value) == "Output path must be set for implementation builds."


def test_build_step_hooks_are_sourced_before_and_after_run_tool():
    build_step_hooks = [
        BuildStepTclHook(tcl_file=Path("pre_synth.tcl"), hook_step="SYNTHESIZE.PRE"),
        BuildStepTclHook(tcl_file=Path("post_synth.tcl"), hook_step="SYNTHESIZE.POST"),
        BuildStepTclHook(tcl_file=Path("pre_pr.tcl"), hook_step="PLACEROUTE.PRE"),
    ]
    tcl = _get_build_tcl(build_step_hooks=build_step_hooks, synth_only=False)

    pre_synth_idx = tcl.index(f"source -notrace {{{to_tcl_path(Path('pre_synth.tcl'))}}}")
    synth_idx = tcl.index("run_tool -name {SYNTHESIZE}")
    post_synth_idx = tcl.index(f"source -notrace {{{to_tcl_path(Path('post_synth.tcl'))}}}")
    pre_pr_idx = tcl.index(f"source -notrace {{{to_tcl_path(Path('pre_pr.tcl'))}}}")
    pr_idx = tcl.index("run_tool -name {PLACEROUTE}")

    assert pre_synth_idx < synth_idx < post_synth_idx < pre_pr_idx < pr_idx


def test_build_step_hooks_with_same_hook_step_are_all_included():
    build_step_hooks = [
        BuildStepTclHook(tcl_file=Path("hook_one.tcl"), hook_step="SYNTHESIZE.PRE"),
        BuildStepTclHook(tcl_file=Path("hook_two.tcl"), hook_step="SYNTHESIZE.PRE"),
    ]
    tcl = _get_build_tcl(build_step_hooks=build_step_hooks, synth_only=True)
    assert f"source -notrace {{{to_tcl_path(Path('hook_one.tcl'))}}}" in tcl
    assert f"source -notrace {{{to_tcl_path(Path('hook_two.tcl'))}}}" in tcl


def test_no_build_step_hooks_gives_no_source():
    assert "source -notrace" not in _get_build_tcl(synth_only=True)
