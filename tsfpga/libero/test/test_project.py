# --------------------------------------------------------------------------------------------------
# Copyright (c) Lukas Vik. All rights reserved.
#
# This file is part of the tsfpga project, a project platform for modern FPGA development.
# https://tsfpga.com
# https://github.com/tsfpga/tsfpga
# --------------------------------------------------------------------------------------------------

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tsfpga.build_step_tcl_hook import BuildStepTclHook
from tsfpga.constraint import Constraint
from tsfpga.libero.mss import MssConfiguration
from tsfpga.libero.project import LiberoProject
from tsfpga.module import BaseModule
from tsfpga.system_utils import create_directory, create_file
from tsfpga.vivado.project import copy_and_combine_dicts

# ruff: noqa: ARG002


def _get_project(**kwargs):
    kwargs.setdefault("name", "name")
    kwargs.setdefault("modules", [])
    kwargs.setdefault("family", "PolarFire")
    kwargs.setdefault("die", "MPF300TS_ES")
    kwargs.setdefault("package", "FCG1152")
    return LiberoProject(**kwargs)


def test_casting_to_string():
    project = _get_project()
    assert (
        str(project)
        == """\
name
Type:       LiberoProject
Top level:  name_top
Generics:   -
"""
    )

    project = _get_project(top="apa", generics={"hest": True, "zebra": 3})
    assert (
        str(project)
        == """\
name
Type:       LiberoProject
Top level:  apa
Generics:   hest=True, zebra=3
"""
    )

    project = _get_project(apa=123, hest=456)
    assert (
        str(project)
        == """\
name
Type:       LiberoProject
Top level:  name_top
Generics:   -
Arguments:  apa=123, hest=456
"""
    )


def test_modules_list_should_be_copied():
    modules = [1]
    proj = _get_project(modules=modules)

    modules.append(2)
    assert len(proj.modules) == 1


def test_static_generics_dictionary_should_be_copied():
    generics = {"apa": 3}
    proj = _get_project(generics=generics)

    generics["apa"] = False
    assert proj.static_generics["apa"] == 3


def test_constraints_list_should_be_copied():
    constraints = [Constraint(file=Path("1.sdc"))]
    proj = _get_project(constraints=constraints)

    constraints.append(Constraint(file=Path("2.sdc")))
    assert len(proj.constraints) == 1


def test_bad_constraint_type_should_raise_error():
    _get_project(constraints=[Constraint(file=Path("apa.sdc"))])

    with pytest.raises(TypeError) as exception_info:
        _get_project(constraints=["file.sdc"])
    assert str(exception_info.value) == 'Got bad type for "constraints" element: file.sdc'


def test_bad_tcl_sources_type_should_raise_error():
    _get_project(tcl_sources=[Path()])

    with pytest.raises(TypeError) as exception_info:
        _get_project(tcl_sources=["file.tcl"])
    assert str(exception_info.value) == 'Got bad type for "tcl_sources" element: file.tcl'


def test_bad_build_step_hooks_type_should_raise_error():
    _get_project(build_step_hooks=[BuildStepTclHook(tcl_file="", hook_step="")])

    with pytest.raises(TypeError) as exception_info:
        _get_project(build_step_hooks=["file.tcl"])
    assert str(exception_info.value) == 'Got bad type for "build_step_hooks" element: file.tcl'


def test_mss_configurations_list_should_be_copied():
    mss_configurations = [MssConfiguration(cfg_file=Path("1.cfg"))]
    proj = _get_project(mss_configurations=mss_configurations)

    mss_configurations.append(MssConfiguration(cfg_file=Path("2.cfg")))
    assert len(proj.mss_configurations) == 1


def test_bad_mss_configurations_type_should_raise_error():
    _get_project(mss_configurations=[MssConfiguration(cfg_file=Path("apa.cfg"))])

    with pytest.raises(TypeError) as exception_info:
        _get_project(mss_configurations=["mss.cfg"])
    assert str(exception_info.value) == 'Got bad type for "mss_configurations" element: mss.cfg'


def test_top_name():
    assert _get_project().top == "name_top"
    assert _get_project(top="hest").top == "hest"


def test_project_file_name_is_same_as_project_name():
    project_path = Path("projects/apa")
    assert _get_project().project_file(project_path) == project_path / "name.prjx"


def test_create_should_raise_exception_if_project_path_already_exists(tmp_path):
    prjx_path = create_file(tmp_path / "project" / "name.prjx")
    proj = _get_project()
    with pytest.raises(ValueError) as exception_info:
        proj.create(tmp_path / "project")
    assert str(exception_info.value) == f'Project "name" already exists: {prjx_path}'


def test_build_should_raise_exception_if_project_does_not_exist(tmp_path):
    project_path = create_directory(tmp_path / "project")
    proj = _get_project()
    with pytest.raises(ValueError) as exception_info:
        proj.build(project_path, synth_only=True)
    assert (
        str(exception_info.value)
        == f'Project "name" does not exist in the specified location: {project_path / "name.prjx"}'
    )


def test_build_with_impl_run_should_raise_exception_if_no_output_path_is_given(tmp_path):
    project_path = create_directory(tmp_path / "project")
    create_file(project_path / "name.prjx")
    proj = _get_project()
    with pytest.raises(ValueError) as exception_info:
        proj.build(project_path)
    assert str(exception_info.value) == (
        "Must specify 'output_path' when doing an implementation build."
    )


def test_project_create(tmp_path):
    with patch("tsfpga.libero.project.run_libero_tcl", autospec=True) as _:
        assert _get_project().create(tmp_path / "projects" / "apa")
    assert (tmp_path / "projects" / "apa" / "create_libero_project.tcl").exists()


@pytest.fixture
def libero_project_test(tmp_path):
    class LiberoProjectTest:
        def __init__(self):
            self.project_path = tmp_path / "projects" / "apa" / "project"
            self.output_path = tmp_path / "projects" / "apa"
            self.build_time_generics = {}
            self.synth_only = True

            self.mocked_run_libero_tcl = None

        def create(self, project, **other_arguments):
            with patch(
                "tsfpga.libero.project.run_libero_tcl", autospec=True
            ) as self.mocked_run_libero_tcl:
                return project.create(project_path=self.project_path, **other_arguments)

        def build(self, project):
            with patch(
                "tsfpga.libero.project.run_libero_tcl", autospec=True
            ) as self.mocked_run_libero_tcl:
                create_file(self.project_path / "apa.prjx")
                return project.build(
                    project_path=self.project_path,
                    output_path=self.output_path,
                    synth_only=self.synth_only,
                    other_parameter="hest",
                )

    return LiberoProjectTest()


def test_default_pre_create_hook_should_pass(libero_project_test):
    class CustomLiberoProject(LiberoProject):
        pass

    project = CustomLiberoProject(
        name="apa", modules=[], family="PolarFire", die="MPF300TS_ES", package="FCG1152"
    )
    libero_project_test.create(project)
    libero_project_test.mocked_run_libero_tcl.assert_called_once()


def test_project_pre_create_hook_returning_false_should_fail_and_not_call_libero_run(
    libero_project_test,
):
    class CustomLiberoProject(LiberoProject):
        def pre_create(self, **kwargs):
            return False

    project = CustomLiberoProject(
        name="apa", modules=[], family="PolarFire", die="MPF300TS_ES", package="FCG1152"
    )
    assert not libero_project_test.create(project)
    libero_project_test.mocked_run_libero_tcl.assert_not_called()


def test_create_should_call_pre_create_with_correct_parameters(libero_project_test):
    project = _get_project(name="apa", hest=456)
    with patch("tsfpga.libero.project.LiberoProject.pre_create") as mocked_pre_create:
        libero_project_test.create(project, zebra=789)
    mocked_pre_create.assert_called_once_with(
        project_path=libero_project_test.project_path, hest=456, zebra=789
    )
    libero_project_test.mocked_run_libero_tcl.assert_called_once()


def test_build_module_pre_build_hook_and_create_regs_are_called(libero_project_test):
    project = _get_project(
        name="apa", modules=[MagicMock(spec=BaseModule), MagicMock(spec=BaseModule)], apa=123
    )
    build_result = libero_project_test.build(project)
    assert build_result.success

    for module in project.modules:
        module.pre_build.assert_called_once_with(
            project=project,
            other_parameter="hest",
            apa=123,
            project_path=libero_project_test.project_path,
            output_path=libero_project_test.output_path,
            generics={},
            synth_only=libero_project_test.synth_only,
        )
        module.create_register_synthesis_files.assert_called_once()


def test_default_pre_and_post_build_hooks_should_pass(libero_project_test):
    class CustomLiberoProject(LiberoProject):
        pass

    project = CustomLiberoProject(
        name="apa", modules=[], family="PolarFire", die="MPF300TS_ES", package="FCG1152"
    )
    build_result = libero_project_test.build(project)
    assert build_result.success
    libero_project_test.mocked_run_libero_tcl.assert_called_once()


def test_project_pre_build_hook_returning_false_should_fail_and_not_call_libero_run(
    libero_project_test,
):
    class CustomLiberoProject(LiberoProject):
        def pre_build(self, **kwargs):
            return False

    project = CustomLiberoProject(
        name="apa", modules=[], family="PolarFire", die="MPF300TS_ES", package="FCG1152"
    )
    build_result = libero_project_test.build(project)
    assert not build_result.success
    libero_project_test.mocked_run_libero_tcl.assert_not_called()


def test_project_post_build_hook_returning_false_should_fail(libero_project_test):
    class CustomLiberoProject(LiberoProject):
        def post_build(self, **kwargs):
            return False

    project = CustomLiberoProject(
        name="apa", modules=[], family="PolarFire", die="MPF300TS_ES", package="FCG1152"
    )
    build_result = libero_project_test.build(project)
    assert not build_result.success
    libero_project_test.mocked_run_libero_tcl.assert_called_once()


def test_project_build_hooks_should_be_called_with_correct_parameters(libero_project_test):
    project = _get_project(name="apa", generics={"static_generic": 2}, apa=123)
    with (
        patch("tsfpga.libero.project.LiberoProject.pre_build") as mocked_pre_build,
        patch("tsfpga.libero.project.LiberoProject.post_build") as mocked_post_build,
    ):
        libero_project_test.build(project)

    arguments = {
        "project_path": libero_project_test.project_path,
        "output_path": libero_project_test.output_path,
        "generics": {"static_generic": 2},
        "synth_only": libero_project_test.synth_only,
        "other_parameter": "hest",
        "apa": 123,
    }
    mocked_pre_build.assert_called_once_with(**arguments)

    arguments.update(build_result=unittest.mock.ANY)
    mocked_post_build.assert_called_once_with(**arguments)


def test_module_pre_build_hook_returning_false_should_fail_and_not_call_libero(
    libero_project_test,
):
    module = MagicMock(spec=BaseModule)
    module.name = "whatever"
    module.pre_build.return_value = False
    project = _get_project(name="apa", modules=[module])

    build_result = libero_project_test.build(project)
    assert not build_result.success
    libero_project_test.mocked_run_libero_tcl.assert_not_called()


def test_synth_only_build_does_not_set_implementation_run_name(libero_project_test):
    project = _get_project(name="apa")
    libero_project_test.synth_only = True
    build_result = libero_project_test.build(project)
    assert build_result.synthesis_run_name == "SYNTHESIZE"
    assert build_result.implementation_run_name is None


def test_full_build_sets_implementation_run_name(libero_project_test):
    project = _get_project(name="apa")
    libero_project_test.synth_only = False
    build_result = libero_project_test.build(project)
    assert build_result.implementation_run_name == "PLACEROUTE"


def test_copy_and_combine_dict_is_reused_from_vivado_project():
    # 'LiberoProject' reuses 'copy_and_combine_dicts' from the Vivado plugin instead of
    # duplicating it. Sanity check that the function behaves as expected.
    assert copy_and_combine_dicts({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


def test_open_calls_run_libero_gui(tmp_path):
    project_path = create_directory(tmp_path / "project")
    create_file(project_path / "name.prjx")
    project = _get_project()
    with patch("tsfpga.libero.project.run_libero_gui", autospec=True) as mocked_run_libero_gui:
        mocked_run_libero_gui.return_value = True
        assert project.open(project_path)
        mocked_run_libero_gui.assert_called_once_with(None, project_path / "name.prjx")
