export const meta = {
  name: 'hugeicons-manifest-build',
  description: 'Generate category + 10 keywords + a description per Hugeicons stroke-rounded icon, batched for parallel fan-out',
  phases: [
    { title: 'Generate' },
    { title: 'Retry' },
  ],
}

const ICON_SCHEMA = {
  type: 'object',
  properties: {
    icons: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          category: { type: 'string' },
          keywords: {
            type: 'array',
            items: { type: 'string' },
            minItems: 10,
            maxItems: 10,
          },
          description: { type: 'string' },
        },
        required: ['name', 'category', 'keywords', 'description'],
      },
    },
  },
  required: ['icons'],
}

function chunk(arr, size) {
  const out = []
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size))
  return out
}

function buildPrompt(names) {
  const listing = names.map(n => `- ${n}`).join('\n')
  return `You are cataloging icons from the Hugeicons stroke-rounded free icon set (a professional, currently-shipping stroke-icon library) for a scientific-figure-authoring tool's searchable icon bank. For EACH icon name listed below, infer what it depicts and produce:

1. "category": one short (1-3 word) broad domain label, e.g. "e-commerce", "weather", "hardware", "networking", "file management", "mathematics", "medical", "transportation", "ui navigation", "security", "communication", "ai / ml", "finance", "editing tools".
2. "keywords": exactly 10 distinct, lowercase search keywords a designer or paper author might type to find this icon by CONCEPT (not just restating the name). Mix: the literal subject, close synonyms, the category/domain, common UI/paper use-cases (e.g. "pipeline", "storage", "warning", "throughput"), and adjacent concepts. No duplicate or near-duplicate keywords. Prefer single words; short 2-word phrases are fine when needed for clarity.
3. "description": one plain, concrete sentence describing what the icon visually depicts (not marketing language, not "a beautiful icon of...").

Notes on names: these follow Hugeicons' naming convention, e.g. "shopping-cart-02" is a stylistic variant of "shopping-cart-01" (same concept, different linework) -- keywords and category should mostly overlap across such variants, and the description may note "(alternate style)" for non-01 variants when helpful.

Icon names:
${listing}

Return one entry per name listed above, with "name" copied exactly as given (same order not required, but every name must appear exactly once).`
}

function runBatches(names, batchSize, phaseName) {
  const batches = chunk(names, batchSize)
  return pipeline(
    batches,
    (batch, _item, idx) =>
      agent(buildPrompt(batch), {
        label: `${phaseName.toLowerCase()}-${idx}`,
        phase: phaseName,
        schema: ICON_SCHEMA,
      }).catch(() => null)
  ).then(results => {
    const manifest = {}
    const missing = []
    results.forEach((result, idx) => {
      const batch = batches[idx]
      if (!result || !result.icons) {
        missing.push(...batch)
        return
      }
      const byName = new Map(result.icons.map(e => [e.name, e]))
      batch.forEach(name => {
        const entry = byName.get(name)
        if (!entry) {
          missing.push(name)
          return
        }
        manifest[name] = {
          keywords: entry.keywords,
          description: entry.description,
          category: entry.category,
        }
      })
    })
    return { manifest, missing }
  })
}

const names = args
log(`generating keywords/descriptions for ${names.length} icons`)

phase('Generate')
const first = await runBatches(names, 35, 'Generate')
log(`first pass: ${Object.keys(first.manifest).length} done, ${first.missing.length} missing`)

let manifest = first.manifest
let missing = first.missing

if (missing.length) {
  phase('Retry')
  const retry = await runBatches(missing, 15, 'Retry')
  manifest = { ...manifest, ...retry.manifest }
  missing = retry.missing
  log(`retry pass: ${Object.keys(retry.manifest).length} recovered, ${missing.length} still missing`)
}

log(`final: ${Object.keys(manifest).length} manifest entries, ${missing.length} missing`)
return { manifest, missing, total: names.length }
