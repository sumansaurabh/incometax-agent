export type FieldSchema = {
  key: string;
  label: string;
  required: boolean;
  selectorHint?: string;
  aliases?: string[];
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
  domSignatures?: string[];
  textClues?: string[];
  /**
   * Regex patterns matched against `document.location.pathname + hash`. A single match
   * contributes URL_PATTERN_SCORE — enough on its own to push an adapter above
   * MIN_ADAPTER_SCORE even when the SPA has not yet rendered form fields with stable
   * names. This is the knob that prevents the old "unknown page" sinkhole for hash-routed
   * SPA pages like /dashboard/fileIncomeTaxReturn.
   */
  urlPatterns?: RegExp[];
};

export const MIN_ADAPTER_SCORE = 8;
export const URL_PATTERN_SCORE = 12;

function normalize(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function textContent(node: Element | null | undefined): string {
  return normalize(node?.textContent ?? "");
}

function escapeAttributeValue(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function firstMatchingSelector(doc: Document, selectorHint?: string): string | undefined {
  if (!selectorHint) {
    return undefined;
  }

  const selectors = selectorHint
    .split(",")
    .map((selector) => selector.trim())
    .filter(Boolean);

  for (const selector of selectors) {
    try {
      if (doc.querySelector(selector)) {
        return selector;
      }
    } catch {
      continue;
    }
  }

  return selectors[0];
}

function selectorExists(doc: Document, selector?: string): boolean {
  if (!selector) {
    return false;
  }
  try {
    return Boolean(doc.querySelector(selector));
  } catch {
    return false;
  }
}

function buildFieldCandidates(field: FieldSchema): string[] {
  return Array.from(
    new Set(
      [
        field.label,
        field.key.replace(/_/g, " "),
        ...(field.aliases ?? []),
      ]
        .map(normalize)
        .filter(Boolean)
    )
  );
}

function selectorForInputElement(node: Element | null): string | undefined {
  if (!node) {
    return undefined;
  }
  const input = node.matches("input, select, textarea")
    ? (node as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement)
    : node.querySelector<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>("input, select, textarea");

  if (!input) {
    return undefined;
  }
  if (input.id) {
    return `#${input.id}`;
  }
  if (input.name) {
    return `${input.tagName.toLowerCase()}[name="${escapeAttributeValue(input.name)}"]`;
  }
  const dataField = input.getAttribute("data-field");
  if (dataField) {
    return `${input.tagName.toLowerCase()}[data-field="${escapeAttributeValue(dataField)}"]`;
  }
  const testId = input.getAttribute("data-testid");
  if (testId) {
    return `${input.tagName.toLowerCase()}[data-testid="${escapeAttributeValue(testId)}"]`;
  }
  return undefined;
}

function inferSelectorFromLabels(doc: Document, candidates: string[]): string | undefined {
  const labelNodes = Array.from(doc.querySelectorAll("label, th, td, span, div, p, legend"));

  for (const node of labelNodes) {
    const content = textContent(node);
    if (!content) {
      continue;
    }
    const matches = candidates.some((candidate) => content === candidate || content.includes(candidate));
    if (!matches) {
      continue;
    }

    if (node.tagName.toLowerCase() === "label") {
      const htmlFor = node.getAttribute("for");
      if (htmlFor) {
        return `#${htmlFor}`;
      }
    }

    const selector = selectorForInputElement(node.closest("tr, fieldset, .form-group, .field, .input-group, div, section"));
    if (selector) {
      return selector;
    }
  }

  return undefined;
}

function inferSelectorFromAttributes(doc: Document, candidates: string[]): string | undefined {
  const attrSelectors = candidates.flatMap((candidate) => {
    const safe = escapeAttributeValue(candidate);
    return [
      `input[aria-label*="${safe}" i], select[aria-label*="${safe}" i], textarea[aria-label*="${safe}" i]`,
      `input[placeholder*="${safe}" i], select[placeholder*="${safe}" i], textarea[placeholder*="${safe}" i]`,
      `input[name*="${safe.replace(/ /g, "")}" i], select[name*="${safe.replace(/ /g, "")}" i], textarea[name*="${safe.replace(/ /g, "")}" i]`,
      `input[id*="${safe.replace(/ /g, "")}" i], select[id*="${safe.replace(/ /g, "")}" i], textarea[id*="${safe.replace(/ /g, "")}" i]`,
      `[data-field*="${safe.replace(/ /g, "_")}" i] input, [data-field*="${safe.replace(/ /g, "_")}" i] select, [data-field*="${safe.replace(/ /g, "_")}" i] textarea`,
    ];
  });

  for (const selector of attrSelectors) {
    try {
      const match = doc.querySelector(selector);
      const resolved = selectorForInputElement(match);
      if (resolved) {
        return resolved;
      }
    } catch {
      continue;
    }
  }

  return undefined;
}

function resolveSelectorHint(doc: Document, field: FieldSchema): string | undefined {
  const explicit = firstMatchingSelector(doc, field.selectorHint);
  if (selectorExists(doc, explicit)) {
    return explicit;
  }

  const candidates = buildFieldCandidates(field);
  return inferSelectorFromLabels(doc, candidates) ?? inferSelectorFromAttributes(doc, candidates) ?? explicit;
}

function resolveSchema(doc: Document, definition: StaticAdapterDefinition): FieldSchema[] {
  return definition.schema.map((field) => ({
    ...field,
    selectorHint: resolveSelectorHint(doc, field),
  }));
}

function matchCount(value: string, patterns: string[]): number {
  return patterns.reduce((count, pattern) => count + (value.includes(normalize(pattern)) ? 1 : 0), 0);
}

function adapterScore(doc: Document, definition: StaticAdapterDefinition): number {
  const title = normalize(doc.title);
  const url = normalize(doc.location.href);
  const body = normalize(doc.body?.innerText ?? doc.body?.textContent ?? "");

  let score = 0;
  score += matchCount(title, definition.keywords) * 5;
  score += matchCount(url, definition.keywords) * 4;
  score += matchCount(body, definition.keywords) * 2;

  if (definition.urlPatterns?.length) {
    const routeSource = `${doc.location.pathname}${doc.location.hash}${doc.location.search}`;
    for (const pattern of definition.urlPatterns) {
      if (pattern.test(routeSource)) {
        score += URL_PATTERN_SCORE;
      }
    }
  }

  if (definition.textClues?.length) {
    score += matchCount(body, definition.textClues) * 2;
  }

  if (definition.domSignatures?.length) {
    for (const selector of definition.domSignatures) {
      if (selectorExists(doc, selector)) {
        score += 6;
      }
    }
  }

  const resolvedSchema = resolveSchema(doc, definition);
  score += resolvedSchema.filter((field) => selectorExists(doc, field.selectorHint)).length * 4;
  score += resolvedSchema.filter((field) => !field.selectorHint && buildFieldCandidates(field).some((candidate) => body.includes(candidate))).length;

  return score;
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
  return {
    key: definition.key,
    detect: (doc) => adapterScore(doc, definition) >= MIN_ADAPTER_SCORE,
    getFormSchema: (doc) => resolveSchema(doc, definition),
    readValidation: (doc) => readDefaultValidation(doc),
  };
}

export function scoreStaticAdapter(doc: Document, definition: StaticAdapterDefinition): number {
  return adapterScore(doc, definition);
}
