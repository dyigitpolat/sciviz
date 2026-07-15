# Hugeicons stroke-rounded icon bank

Vendored SVG assets backing the Hugeicons half of `sciviz.Icon` (see
`sciviz/_assets/_hugeicons.py`).

## Provenance

- **Source set**: Hugeicons' free tier, Stroke Rounded style
  (<https://hugeicons.com/icons/stroke-rounded>).
- **Distribution channel**: the official `@hugeicons/core-free-icons` npm
  package (`v4.2.2`, published 2026-06-26), not scraped from the website.
  The live site renders icon previews client-side after JS hydration with
  no public bulk-download endpoint; the npm package is Hugeicons' own
  redistributable channel for this exact icon set.
- **License**: MIT, as declared in `@hugeicons/core-free-icons`'s
  `package.json` and on the npm registry. Attribution: Hugeicons
  (<https://hugeicons.com>).
- **Coverage**: 5,471 icons, vs. 5,995 listed on the live site as of
  2026-07-14. The gap is icons added to the site in the ~2.5 weeks since
  the npm package's last publish and not yet re-packaged upstream. Re-run
  the fetch workflow against a newer `@hugeicons/core-free-icons` release
  to close the gap.

## Structure

- `icons/<name>.svg` -- one standalone, valid SVG per icon (24x24
  viewBox, `stroke="currentColor"` / occasional `fill="currentColor"`
  sub-shapes, per-shape `opacity` where the original design uses it).
  Names are derived from the package's PascalCase export names
  (`ShoppingCart02Icon` -> `shopping-cart-02`); numeric suffixes
  (`-01`, `-02`, ...) denote stylistic variants of the same concept, not
  different concepts.
- `manifest.json` -- `{name: {keywords: [10 strings], description, category}}`.
  All three fields are LLM-generated from the icon name alone (Hugeicons'
  own public search API at `search.hugeicons.com` was tried as a source of
  authoritative category/tag metadata but throttles hard under even light
  concurrency, so pulling it for ~5,500 names was dropped rather than
  either crawling it for over an hour serially or straining a third
  party's free service).

## Rendering

Icons are not eagerly parsed at import time. `sciviz.Icon(name)` checks
the curated Lucide subset first, then this bank; on a hit,
`load_hugeicon_shapes` parses the corresponding SVG once (LRU-cached).
Because these icons can mix `path`/`circle`/`rect`/`ellipse` and vary
`stroke-width`/`opacity` per shape -- unlike Lucide's uniform path-only
icons -- rendering goes through `Canvas.svg_shapes`, not `Canvas.svg_path`.

## Refreshing

See `scripts/hugeicons_refresh/README.md` for the fetch + conversion
script and the saved Workflow script that generates new manifest entries,
to pull in a newer `@hugeicons/core-free-icons` release.
