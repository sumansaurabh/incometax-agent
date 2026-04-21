import { createStaticAdapter, PageAdapter } from "./base";
import { pageCatalog } from "./catalog";

const adapters: PageAdapter[] = pageCatalog.map((definition) => createStaticAdapter(definition));

export function detectAdapter(doc: Document): PageAdapter | null {
  return adapters.find((adapter) => adapter.detect(doc)) ?? null;
}

export { adapters };
