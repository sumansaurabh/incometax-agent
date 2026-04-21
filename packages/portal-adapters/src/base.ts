export type FieldSchema = {
  key: string;
  label: string;
  required: boolean;
  selectorHint?: string;
};

export type ValidationError = {
  field: string;
  message: string;
};

export type PageAdapter = {
  key: string;
  detect: (doc: Document) => boolean;
  getFormSchema: (doc: Document) => FieldSchema[];
  readValidation: (doc: Document) => ValidationError[];
};

export type StaticAdapterDefinition = {
  key: string;
  keywords: string[];
  schema: FieldSchema[];
};

function normalize(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function inferFieldName(node: Element): string {
  const candidate =
    node.getAttribute("data-field") ??
    node.getAttribute("name") ??
    node.getAttribute("id") ??
    node.closest("[data-field],[name],[id]")?.getAttribute("data-field") ??
    node.closest("[data-field],[name],[id]")?.getAttribute("name") ??
    node.closest("[data-field],[name],[id]")?.getAttribute("id");

  return candidate || "unknown";
}

export function readDefaultValidation(doc: Document): ValidationError[] {
  const nodes = Array.from(
    doc.querySelectorAll(".error, .validation-error, [role='alert'], [aria-invalid='true']")
  );

  return nodes
    .map((node) => ({
      field: inferFieldName(node),
      message: node.textContent?.trim() ?? "",
    }))
    .filter((item) => item.message.length > 0);
}

export function createStaticAdapter(definition: StaticAdapterDefinition): PageAdapter {
  const normalizedKeywords = definition.keywords.map(normalize);
  return {
    key: definition.key,
    detect: (doc) => {
      const title = normalize(doc.title);
      const url = normalize(doc.location.href);
      return normalizedKeywords.some((keyword) => title.includes(keyword) || url.includes(keyword));
    },
    getFormSchema: () => definition.schema,
    readValidation: (doc) => readDefaultValidation(doc),
  };
}
