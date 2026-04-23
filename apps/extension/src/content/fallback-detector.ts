import { FieldSchema, ValidationError } from "@itx/portal-adapters";

export type FallbackSnapshot = {
  page: string;
  heading: string | null;
  fields: FieldSchema[];
  validationErrors: ValidationError[];
  score: number;
};

const MAX_FIELDS = 40;
const MAX_ERRORS = 20;

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

function resolveLabelForInput(node: Element): string | null {
  const ariaLabel = node.getAttribute("aria-label");
  if (ariaLabel) return ariaLabel.trim().slice(0, 200);

  const labelledBy = node.getAttribute("aria-labelledby");
  if (labelledBy) {
    const referenced = document.getElementById(labelledBy);
    if (referenced?.textContent) return referenced.textContent.trim().slice(0, 200);
  }

  const id = node.getAttribute("id");
  if (id) {
    const explicit = document.querySelector(`label[for="${id.replace(/"/g, '\\"')}"]`);
    if (explicit?.textContent) return explicit.textContent.trim().slice(0, 200);
  }

  const wrapping = node.closest("label");
  if (wrapping?.textContent) return wrapping.textContent.trim().slice(0, 200);

  const placeholder = node.getAttribute("placeholder");
  if (placeholder) return placeholder.trim().slice(0, 200);

  const nameAttr = node.getAttribute("name");
  if (nameAttr) return nameAttr;

  return null;
}

function buildSelectorForInput(node: Element): string | undefined {
  if (node.id) return `#${CSS.escape(node.id)}`;
  const name = node.getAttribute("name");
  if (name) return `${node.tagName.toLowerCase()}[name="${name.replace(/"/g, '\\"')}"]`;
  const dataField = node.getAttribute("data-field");
  if (dataField) return `[data-field="${dataField.replace(/"/g, '\\"')}"]`;
  const testId = node.getAttribute("data-testid");
  if (testId) return `[data-testid="${testId.replace(/"/g, '\\"')}"]`;
  return undefined;
}

function collectFields(doc: Document): FieldSchema[] {
  const nodes = Array.from(doc.querySelectorAll("input, select, textarea, [role='combobox'], [role='listbox'], [role='textbox']"));
  const fields: FieldSchema[] = [];
  const seenSelectors = new Set<string>();
  const seenLabels = new Set<string>();

  for (const node of nodes) {
    if (fields.length >= MAX_FIELDS) break;

    // Skip clearly invisible inputs (hidden / off-screen / display:none)
    if (node instanceof HTMLInputElement && node.type === "hidden") continue;
    const style = (node.ownerDocument?.defaultView ?? window).getComputedStyle(node as HTMLElement);
    if (style.display === "none" || style.visibility === "hidden") continue;

    const label = resolveLabelForInput(node);
    if (!label) continue;

    const selector = buildSelectorForInput(node);
    const dedupKey = selector ?? label;
    if (seenSelectors.has(dedupKey) || seenLabels.has(label)) continue;
    seenSelectors.add(dedupKey);
    seenLabels.add(label);

    const required = node.hasAttribute("required") || node.getAttribute("aria-required") === "true";

    fields.push({
      key: slugify(label) || "field",
      label,
      required,
      selectorHint: selector,
    });
  }

  return fields;
}

function collectValidationErrors(doc: Document): ValidationError[] {
  const nodes = Array.from(
    doc.querySelectorAll(".error, .validation-error, .mat-error, [role='alert'], [aria-invalid='true']")
  );
  const errors: ValidationError[] = [];
  for (const node of nodes) {
    if (errors.length >= MAX_ERRORS) break;
    const message = (node.textContent ?? "").trim();
    if (!message) continue;
    const fieldAttr =
      node.getAttribute("data-field") ??
      node.getAttribute("name") ??
      node.getAttribute("id") ??
      node.closest("[data-field],[name],[id]")?.getAttribute("data-field") ??
      node.closest("[data-field],[name],[id]")?.getAttribute("name") ??
      node.closest("[data-field],[name],[id]")?.getAttribute("id") ??
      "unknown";
    errors.push({ field: fieldAttr, message: message.slice(0, 500) });
  }
  return errors;
}

function primaryHeading(doc: Document): string | null {
  const candidate = doc.querySelector("h1, h2, [role='heading']");
  const text = candidate?.textContent?.trim();
  return text ? text.slice(0, 200) : null;
}

export function buildFallbackSnapshot(doc: Document): FallbackSnapshot | null {
  const heading = primaryHeading(doc);
  const fields = collectFields(doc);
  const validationErrors = collectValidationErrors(doc);

  // Score reflects how useful this fallback is. Agent can use it to decide whether to call
  // capture_viewport — heading + fields → strong; heading alone → weak; nothing → return null.
  let score = 0;
  if (heading) score += 3;
  score += Math.min(fields.length, 10);
  score += Math.min(validationErrors.length, 3);

  if (score === 0) return null;

  const page = heading ? `generic:${slugify(heading)}` : "generic:unknown";

  return {
    page,
    heading,
    fields,
    validationErrors,
    score,
  };
}
