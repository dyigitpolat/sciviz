# Refreshing the Hugeicons bank

The bank at `sciviz/_assets/hugeicons/` (icons + `manifest.json`) was built
once from `@hugeicons/core-free-icons` v4.2.2 (5,471 icons; the live
hugeicons.com listing showed 5,995 as of 2026-07-14 -- the gap is icons
added since that npm publish). To pull in a newer package release:

1. **Fetch + convert.** No public bulk-SVG endpoint exists for hugeicons.com
   itself (the site renders previews client-side after JS hydration); pull
   from the official npm distribution instead:

   ```bash
   npm pack @hugeicons/core-free-icons
   mkdir -p /tmp/hugeicons-pkg && tar -xzf hugeicons-core-free-icons-*.tgz -C /tmp/hugeicons-pkg
   python3 convert_icons.py /tmp/hugeicons-pkg/package/dist/esm ../../sciviz/_assets/hugeicons/icons
   ```

   This overwrites existing `.svg` files and adds new ones; it never
   deletes, so check `git status` afterward to see what's new/changed.

2. **Generate manifest entries for new icons only.** Diff the new SVG
   filenames against the existing `manifest.json` keys to get a list of
   names lacking an entry, then run the Workflow tool:

   ```
   Workflow({ scriptPath: "build_manifest_workflow.js", args: newNames })
   ```

   `args` must be a plain array of icon name strings (not a JSON-encoded
   string). The script batches them (35/agent call, retries failures at
   15/call) and returns `{ manifest, missing, total }` -- merge `manifest`
   into the existing `manifest.json` (new keys only; don't regenerate
   existing entries, they're stable).

3. Re-run `sciviz/tests/test_hugeicons_bank.py` to confirm the bank and
   manifest stay in sync.

See `sciviz/_assets/hugeicons/README.md` for provenance/licensing details,
and why the `search.hugeicons.com` search API isn't part of this
pipeline (it throttles hard under concurrency -- not worth crawling for
~5,500 names).
