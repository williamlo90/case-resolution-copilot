from scripts.check_migration_graph import inspect_migration_graph


def test_migration_graph_has_one_current_head_and_base() -> None:
    summary = inspect_migration_graph()

    assert summary.head == "20260730_0019"
    assert summary.base == "20260703_0001"
    assert summary.revisions == 19
