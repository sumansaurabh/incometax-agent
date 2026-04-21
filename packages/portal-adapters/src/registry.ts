import { createStaticAdapter, PageAdapter, scoreStaticAdapter } from "./base";
import { pageCatalog } from "./catalog";

const adapters: PageAdapter[] = pageCatalog.map((definition) => createStaticAdapter(definition));

export function detectAdapter(doc: Document): PageAdapter | null {
  let bestAdapter: PageAdapter | null = null;
  let bestScore = 0;

  for (let i = 0; i < pageCatalog.length; i += 1) {
    const score = scoreStaticAdapter(doc, pageCatalog[i]);
    if (score > bestScore) {
      bestScore = score;
      bestAdapter = adapters[i];
    }
  }

  return bestScore > 0 ? bestAdapter : null;
}

export { adapters };
