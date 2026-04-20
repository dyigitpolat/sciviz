# Gallery reference figures

Each file `figNN.png` is a user-supplied scientific diagram that the
corresponding `gallery/figNN.py` is expected to reproduce (or deliberately
reinterpret) using only public `sciviz` API.

These images serve as pixel-level acceptance targets during the
[ten-of-ten](../../plans/ten-of-ten.md) rollout: they demonstrate that a
single authoring document is genuinely enough to express a full range of
paper figures in a small number of lines.

| Reference         | Gallery                                     | Primary feature exercised                                          |
| ----------------- | ------------------------------------------- | ------------------------------------------------------------------ |
| `fig01.png`       | [`gallery/fig01.py`](../fig01.py)           | `Image` embedding + `Brace.spanning`                               |
| `fig02.png`       | [`gallery/fig02.py`](../fig02.py)           | Existing primitives + structured text runs                         |
| `fig03.png`       | [`gallery/fig03.py`](../fig03.py)           | Grouped vertical bar chart + multi-tier data/role explainer        |
| `fig04.png`       | [`gallery/fig04.py`](../fig04.py)           | `AlignedStack` cross-parent column alignment                       |
| `fig05.png`       | [`gallery/fig05.py`](../fig05.py)           | `Region` corner badges + structured text runs                      |
| `fig06.png`       | [`gallery/fig06.py`](../fig06.py)           | `LineChart` with annotations                                       |
| `fig07.png`       | [`gallery/fig07.py`](../fig07.py)           | `Tree` with per-edge color                                         |
| `fig08.png`       | [`gallery/fig08.py`](../fig08.py)           | `Icon` + `Brace.spanning` on a pipeline                            |
| `fig09.png`       | [`gallery/fig09.py`](../fig09.py)           | Icon-heavy composition                                             |
| `fig10.png`       | [`gallery/fig10.py`](../fig10.py)           | `Separator` + `AlignedStack`                                       |

When the source PNGs are placed in this directory, they are ignored by
pytest but checked into git so future contributors can see exactly what
each demonstrative figure was built against.
