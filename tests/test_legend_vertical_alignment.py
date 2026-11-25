"""A vertical key is a list: labels start at one x whatever the swatch width."""
from sciviz import DEFAULT_THEME, Icon, Legend, LegendItem, Marker


def test_vertical_legend_items_share_a_swatch_slot():
    items = [LegendItem(Icon("sparkles", size=12.0), "wide swatch"),
             LegendItem(Marker("square", size="sm"), "narrow swatch")]
    Legend(*items, orientation="vertical").measure(DEFAULT_THEME)
    widths = {round(i.swatch.measure(DEFAULT_THEME).w, 3) for i in items}
    assert len(widths) == 2                      # the swatches differ ...
    assert items[0]._slot_w == items[1]._slot_w  # ... their slot does not
    assert items[0]._slot_w == max(widths)
