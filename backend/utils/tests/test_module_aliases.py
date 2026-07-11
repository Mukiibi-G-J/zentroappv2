from utils.modules import (
    dedupe_enabled_modules,
    plan_includes_module,
)


def test_sales_plan_covers_pos_override():
    assert plan_includes_module(["sales", "inventory"], "pos") is True


def test_prune_pos_override_when_sales_on_plan():
    overrides = ["pos", "restaurant"]
    pruned = [m for m in overrides if not plan_includes_module(["sales"], m)]
    assert pruned == ["restaurant"]


def test_dedupe_enabled_modules_drops_pos_when_sales_present():
    assert dedupe_enabled_modules(["sales", "pos", "inventory"]) == [
        "sales",
        "inventory",
    ]
