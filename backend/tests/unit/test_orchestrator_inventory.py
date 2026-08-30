from scripts.inspect_orchestrator_frameworks import framework_inventory


def test_framework_inventory_is_honest_about_runtime_roles() -> None:
    report = {item.framework: item for item in framework_inventory()}

    assert report["LangGraph"].production_default is True
    assert "Production" in report["LangGraph"].role
    assert report["LangChain Core"].production_default is False
    assert "Prompt templates" in report["LangChain Core"].role
    assert report["CrewAI"].production_default is False
    assert "prototype" in report["CrewAI"].role
    assert report["AutoGen"].production_default is False
    assert "prototype" in report["AutoGen"].role
