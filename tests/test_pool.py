"""Basic CRUD + applicable_to filter tests for the shared pool."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.morning_brief.pool import FieldsCategoriesPool


async def test_add_list_filter_remove_fields(hass: HomeAssistant) -> None:
    """Add → list → filter by entry → remove → list again."""
    pool = FieldsCategoriesPool(hass)
    await pool.async_load()

    # Empty initially
    assert pool.list_fields() == []
    assert pool.list_categories() == []

    # Add a field visible only in entry_A
    id_a = await pool.async_add_field(
        {"field_id": "steps", "label": "Steps"},
        applicable_to=["entry_A"],
    )
    # Add a field visible in everyone (applicable_to=[])
    id_universal = await pool.async_add_field(
        {"field_id": "weight", "label": "Weight"},
        applicable_to=[],
    )

    fields = pool.list_fields()
    assert len(fields) == 2
    ids = {f["id"] for f in fields}
    assert ids == {id_a, id_universal}

    # Filter: entry_A sees both (its own + universal)
    for_a = pool.fields_for_entry("entry_A")
    assert len(for_a) == 2
    # Filter: entry_B sees only the universal one
    for_b = pool.fields_for_entry("entry_B")
    assert len(for_b) == 1
    assert for_b[0]["id"] == id_universal

    # Remove and re-list
    assert await pool.async_remove_field(id_a) is True
    assert await pool.async_remove_field("non-existent") is False
    assert len(pool.list_fields()) == 1


async def test_update_applicable_to(hass: HomeAssistant) -> None:
    """Editing applicable_to changes the filter result."""
    pool = FieldsCategoriesPool(hass)
    await pool.async_load()
    item_id = await pool.async_add_category(
        {"category_id": "cat1", "label": "Cat 1"},
        applicable_to=["entry_X"],
    )

    # Only entry_X sees it
    assert len(pool.categories_for_entry("entry_X")) == 1
    assert len(pool.categories_for_entry("entry_Y")) == 0

    # Broaden visibility
    await pool.async_update_category(
        item_id, applicable_to=["entry_X", "entry_Y"]
    )
    assert len(pool.categories_for_entry("entry_X")) == 1
    assert len(pool.categories_for_entry("entry_Y")) == 1

    # Make universal
    await pool.async_update_category(item_id, applicable_to=[])
    assert len(pool.categories_for_entry("entry_Z")) == 1


async def test_update_data_only(hass: HomeAssistant) -> None:
    """Updating just the data leaves applicable_to untouched."""
    pool = FieldsCategoriesPool(hass)
    await pool.async_load()
    item_id = await pool.async_add_field(
        {"field_id": "f1", "label": "Old"},
        applicable_to=["entry_A"],
    )

    await pool.async_update_field(item_id, data={"field_id": "f1", "label": "New"})

    fields = pool.list_fields()
    assert fields[0]["data"]["label"] == "New"
    assert fields[0]["applicable_to"] == ["entry_A"]


async def test_update_nonexistent_is_noop(hass: HomeAssistant) -> None:
    """Updating an unknown item doesn't crash, just logs a warning."""
    pool = FieldsCategoriesPool(hass)
    await pool.async_load()
    # Should not raise
    await pool.async_update_field("nope", data={"x": 1})
    await pool.async_update_category("nope", applicable_to=["a"])
    assert pool.list_fields() == []
    assert pool.list_categories() == []
