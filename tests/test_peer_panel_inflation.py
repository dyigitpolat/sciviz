"""Peer layouts must equalise painted containers, not empty slots."""

from __future__ import annotations

from sciviz import BlockGroup, Box, Canvas, Column, EqualGrid, Row, Theme


def test_block_group_honours_outer_inflation_floor():
    theme = Theme()
    group = BlockGroup(Box("short"), label="stage", dashed=False)
    group.inflate_to(220, 120)
    size = group.measure(theme)
    assert size.w == 220
    assert size.h == 120


def test_equal_grid_width_reaches_equal_width_column_children():
    theme = Theme()
    narrow_panel = BlockGroup(Box("A"), label="module", dashed=False)
    narrow = Column(
        Box("head"), narrow_panel, Box("foot"),
        equal_widths=True,
    )
    wide_panel = BlockGroup(Box("a substantially wider module"),
                            label="module", dashed=False)
    wide = Column(
        Box("a substantially wider head"), wide_panel,
        Box("a substantially wider foot"),
        equal_widths=True,
    )
    grid = EqualGrid(narrow, wide, columns=2, equal="width")
    grid.measure(theme)

    target = wide.measure(theme).w
    assert narrow.measure(theme).w == target
    assert narrow.children[0].measure(theme).w == target
    assert narrow_panel.measure(theme).w == target
    # Measurement is stable: container padding is not re-added per pass.
    assert grid.measure(theme) == grid.measure(theme)


def test_stretched_stage_column_gives_surplus_height_to_panel():
    theme = Theme()
    short_panel = BlockGroup(Box("short"), label="stage", dashed=False)
    short = Column(Box("head"), short_panel, Box("foot"), gap="sm")
    tall_panel = BlockGroup(
        Column(Box("one"), Box("two"), Box("three"), gap="md"),
        label="stage",
        dashed=False,
    )
    tall = Column(Box("head"), tall_panel, Box("foot"), gap="sm")
    row = Row(short, tall, align="stretch")
    row.measure(theme)

    assert short.measure(theme).h == tall.measure(theme).h
    assert short_panel.measure(theme).h == tall_panel.measure(theme).h
    # Repeated layout passes must not keep adding the same surplus.
    assert row.measure(theme) == row.measure(theme)


def test_nested_stage_row_stretches_column_but_centres_accessory():
    theme = Theme()
    panel = BlockGroup(Box("module"), label="stage", dashed=False)
    stage = Column(Box("head"), panel, Box("foot"), gap="sm")
    accessory = Box("cache")
    accessory_height = accessory.measure(theme).h
    nested = Row(stage, accessory, align="center")
    target = nested.measure(theme).h + 100
    nested.inflate_to(0, target)

    assert nested.measure(theme).h == target
    assert stage.measure(theme).h == target
    assert accessory.measure(theme).h == accessory_height
    assert nested.measure(theme) == nested.measure(theme)


def test_light_block_group_border_does_not_make_label_unreadable():
    theme = Theme()
    group = BlockGroup(
        Box("body"), label="Readable title", color="border", dashed=False
    )
    canvas = Canvas()
    group.render(canvas, 0, 0, theme)
    svg = canvas.to_svg(300, 120)
    assert f'fill="{theme.color_of("text_muted")}"' in svg
