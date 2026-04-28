from __future__ import annotations

from analysis_service.modules.prompt_builder import SYSTEM_PREFIX, build_prompt


def test_prompt_ordering_all_sections() -> None:
    result = build_prompt(
        bc_config_yaml="yaml content here",
        module_instructions="do analysis",
        variable_data="keyword: test",
    )
    sys_idx = result.index(SYSTEM_PREFIX)
    bc_idx = result.index("BC BEST PRACTICES CONFIGURATION:")
    task_idx = result.index("TASK:")
    data_idx = result.index("DATA:")
    assert sys_idx < bc_idx < task_idx < data_idx


def test_prompt_without_bc_config() -> None:
    result = build_prompt(module_instructions="do analysis", variable_data="keyword: test")
    assert "BC BEST PRACTICES CONFIGURATION:" not in result
    assert "TASK:" in result
    assert "DATA:" in result


def test_static_prefix_before_variable_data() -> None:
    result = build_prompt(module_instructions="instructions", variable_data="variable stuff")
    sys_idx = result.index(SYSTEM_PREFIX)
    data_idx = result.index("variable stuff")
    assert sys_idx < data_idx


def test_bc_config_between_system_and_task() -> None:
    result = build_prompt(
        bc_config_yaml="rules here",
        module_instructions="task",
        variable_data="data",
    )
    bc_idx = result.index("BC BEST PRACTICES CONFIGURATION:")
    task_idx = result.index("TASK:")
    assert bc_idx < task_idx


def test_task_header_present() -> None:
    result = build_prompt(module_instructions="analyze page", variable_data="data")
    assert "\n\nTASK:\nanalyze page" in result


def test_data_header_present() -> None:
    result = build_prompt(module_instructions="task", variable_data="keyword: casino")
    assert "\n\nDATA:\nkeyword: casino" in result


def test_bc_config_header() -> None:
    result = build_prompt(
        bc_config_yaml="version: 1.0",
        module_instructions="t",
        variable_data="d",
    )
    assert "\n\nBC BEST PRACTICES CONFIGURATION:\nversion: 1.0" in result


def test_empty_variable_data_still_has_header() -> None:
    result = build_prompt(module_instructions="task", variable_data="")
    assert "\n\nDATA:\n" in result
