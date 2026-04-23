import { detectAdapter, FieldSchema, ValidationError } from "@itx/portal-adapters";
import { readField } from "./actions/read";
import { buildFallbackSnapshot, FallbackSnapshot } from "./fallback-detector";

export type FocusedField = {
  selector: string;
  tag: "input" | "select" | "textarea" | "button" | "other";
  label: string | null;
  value: string | null;
  role: string | null;
  ariaExpanded: boolean;
};

export type OpenDropdownOption = {
  value: string | null;
  label: string;
  selected: boolean;
};

export type OpenDropdown = {
  triggerSelector: string;
  label: string | null;
  options: OpenDropdownOption[];
};

export type PageDetectionSignal = {
  score: number;
  matched: "adapter" | "fallback" | "none";
  adapterKey: string | null;
};

export type PageSnapshot = {
  page: string;
  title: string;
  url: string;
  route: string;
  headings: string[];
  focusedField: FocusedField | null;
  openDropdown: OpenDropdown | null;
  fields: FieldSchema[];
  validationErrors: ValidationError[];
  portalState: {
    page: string;
    fields: Record<string, { value: string | null; fieldKey: string; label: string; required: boolean }>;
    validationErrors: ValidationError[];
    openDropdown: OpenDropdown | null;
    focusedField: FocusedField | null;
  };
  pageDetection: PageDetectionSignal;
  fallback: FallbackSnapshot | null;
  capturedAt: string;
};

type Listener = (snapshot: PageSnapshot) => void;

const MAX_HEADINGS = 6;
const MAX_DROPDOWN_OPTIONS = 50;

function normalizeRoute(url: URL): string {
  const hash = url.hash.replace(/^#/, "");
  if (hash) {
    return hash.split("?")[0];
  }
  return url.pathname;
}

function collectHeadings(doc: Document): string[] {
  const nodes = Array.from(doc.querySelectorAll("h1, h2, [role='heading'], .step-indicator .active, .stepper .active"));
  const seen = new Set<string>();
  const results: string[] = [];
  for (const node of nodes) {
    const text = (node.textContent ?? "").replace(/\s+/g, " ").trim();
    if (!text || seen.has(text)) continue;
    seen.add(text);
    results.push(text.slice(0, 200));
    if (results.length >= MAX_HEADINGS) break;
  }
  return results;
}

function describeTag(node: Element): FocusedField["tag"] {
  const tag = node.tagName.toLowerCase();
  if (tag === "input" || tag === "select" || tag === "textarea" || tag === "button") {
    return tag;
  }
  return "other";
}

function buildSelectorForElement(node: Element): string {
  if (node.id) {
    return `#${CSS.escape(node.id)}`;
  }
  const name = node.getAttribute("name");
  if (name) {
    return `${node.tagName.toLowerCase()}[name="${name.replace(/"/g, '\\"')}"]`;
  }
  const dataField = node.getAttribute("data-field");
  if (dataField) {
    return `[data-field="${dataField.replace(/"/g, '\\"')}"]`;
  }
  const testId = node.getAttribute("data-testid");
  if (testId) {
    return `[data-testid="${testId.replace(/"/g, '\\"')}"]`;
  }
  // last resort — tag + position
  const parent = node.parentElement;
  if (!parent) return node.tagName.toLowerCase();
  const siblings = Array.from(parent.children).filter((child) => child.tagName === node.tagName);
  const index = siblings.indexOf(node);
  return `${node.tagName.toLowerCase()}:nth-of-type(${index + 1})`;
}

function resolveLabelForField(node: Element): string | null {
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

  return null;
}

function captureFocusedField(): FocusedField | null {
  const active = document.activeElement;
  if (!active || active === document.body) return null;
  const tag = describeTag(active);
  if (tag === "other") {
    // Only capture interactive-ish nodes. A focused <div> without a role is noise.
    const role = active.getAttribute("role");
    if (!role || !["combobox", "listbox", "textbox", "button"].includes(role)) return null;
  }

  const el = active as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement | HTMLElement;
  const value = "value" in el && typeof (el as HTMLInputElement).value === "string" ? (el as HTMLInputElement).value : null;

  return {
    selector: buildSelectorForElement(active),
    tag,
    label: resolveLabelForField(active),
    value: value ? value.slice(0, 500) : null,
    role: active.getAttribute("role"),
    ariaExpanded: active.getAttribute("aria-expanded") === "true",
  };
}

function captureNativeSelectOptions(select: HTMLSelectElement): OpenDropdownOption[] {
  return Array.from(select.options)
    .slice(0, MAX_DROPDOWN_OPTIONS)
    .map((option) => ({
      value: option.value || null,
      label: (option.textContent ?? "").trim(),
      selected: option.selected,
    }));
}

function captureAriaListboxOptions(listbox: Element): OpenDropdownOption[] {
  const nodes = Array.from(listbox.querySelectorAll("[role='option'], li, mat-option"));
  const results: OpenDropdownOption[] = [];
  for (const node of nodes) {
    if (results.length >= MAX_DROPDOWN_OPTIONS) break;
    const label = (node.textContent ?? "").trim();
    if (!label) continue;
    results.push({
      value: node.getAttribute("data-value") || node.getAttribute("value") || null,
      label,
      selected: node.getAttribute("aria-selected") === "true" || node.classList.contains("selected"),
    });
  }
  return results;
}

function captureOpenDropdown(focused: FocusedField | null): OpenDropdown | null {
  // Native <select> currently focused
  const active = document.activeElement;
  if (active instanceof HTMLSelectElement) {
    return {
      triggerSelector: buildSelectorForElement(active),
      label: resolveLabelForField(active),
      options: captureNativeSelectOptions(active),
    };
  }

  // ARIA combobox with an open listbox
  if (focused?.ariaExpanded) {
    const owns = active?.getAttribute("aria-owns") || active?.getAttribute("aria-controls");
    if (owns) {
      const listbox = document.getElementById(owns);
      if (listbox) {
        const options = captureAriaListboxOptions(listbox);
        if (options.length > 0) {
          return {
            triggerSelector: focused.selector,
            label: focused.label,
            options,
          };
        }
      }
    }
    // Fallback: find any visible listbox in the document
    const listbox = document.querySelector("[role='listbox']:not([hidden])");
    if (listbox) {
      const options = captureAriaListboxOptions(listbox);
      if (options.length > 0) {
        return {
          triggerSelector: focused.selector,
          label: focused.label,
          options,
        };
      }
    }
  }

  // Last resort: any visible open listbox regardless of focus
  const openListbox = document.querySelector("[role='listbox']:not([aria-hidden='true']):not([hidden]), .mat-select-panel:not([hidden]), .cdk-overlay-pane [role='listbox']");
  if (openListbox) {
    const options = captureAriaListboxOptions(openListbox);
    if (options.length > 0) {
      return {
        triggerSelector: buildSelectorForElement(openListbox),
        label: null,
        options,
      };
    }
  }

  return null;
}

function buildSnapshot(): PageSnapshot {
  const adapterContext = (() => {
    const adapter = detectAdapter(document);
    if (!adapter) return null;
    return {
      key: adapter.key,
      fields: adapter.getFormSchema(document),
      validationErrors: adapter.readValidation(document),
    };
  })();

  const fallback = adapterContext ? null : buildFallbackSnapshot(document);

  const focusedField = captureFocusedField();
  const openDropdown = captureOpenDropdown(focusedField);
  const headings = collectHeadings(document);

  const fields = adapterContext?.fields ?? fallback?.fields ?? [];
  const validationErrors = adapterContext?.validationErrors ?? fallback?.validationErrors ?? [];
  const page = adapterContext?.key ?? fallback?.page ?? "unknown";

  const portalFields = Object.fromEntries(
    fields
      .filter((field) => Boolean(field.selectorHint))
      .map((field) => [
        field.selectorHint as string,
        {
          value: readField(field.selectorHint as string),
          fieldKey: field.key,
          label: field.label,
          required: field.required,
        },
      ])
  );

  const pageDetection: PageDetectionSignal = {
    score: adapterContext ? 999 : fallback ? fallback.score : 0,
    matched: adapterContext ? "adapter" : fallback ? "fallback" : "none",
    adapterKey: adapterContext?.key ?? null,
  };

  const url = new URL(window.location.href);

  return {
    page,
    title: document.title,
    url: window.location.href,
    route: normalizeRoute(url),
    headings,
    focusedField,
    openDropdown,
    fields,
    validationErrors,
    portalState: {
      page,
      fields: portalFields,
      validationErrors,
      openDropdown,
      focusedField,
    },
    pageDetection,
    fallback: fallback ?? null,
    capturedAt: new Date().toISOString(),
  };
}

export class PageObserver {
  private listeners = new Set<Listener>();
  private latest: PageSnapshot | null = null;
  private dirty = true;
  private scheduled: number | null = null;
  private mutationObserver: MutationObserver | null = null;
  private lastRoute: string | null = null;
  private lastDropdownKey: string | null = null;

  start(): void {
    this.mutationObserver = new MutationObserver(() => this.markDirty());
    this.mutationObserver.observe(document.documentElement, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["aria-expanded", "aria-hidden", "class", "value"],
    });

    window.addEventListener("hashchange", () => this.onNavigation());
    window.addEventListener("popstate", () => this.onNavigation());
    this.patchHistoryApi();

    document.addEventListener("focusin", () => this.markDirty(), true);
    document.addEventListener("focusout", () => this.markDirty(), true);
    document.addEventListener("click", () => this.markDirty(), true);
    document.addEventListener("change", () => this.markDirty(), true);

    this.refresh();
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    if (this.latest) listener(this.latest);
    return () => this.listeners.delete(listener);
  }

  snapshot(): PageSnapshot {
    if (!this.latest || this.dirty) {
      this.latest = buildSnapshot();
      this.dirty = false;
    }
    return this.latest;
  }

  private patchHistoryApi(): void {
    const original = {
      push: history.pushState.bind(history),
      replace: history.replaceState.bind(history),
    };
    history.pushState = (...args) => {
      const result = original.push(...args);
      this.onNavigation();
      return result;
    };
    history.replaceState = (...args) => {
      const result = original.replace(...args);
      this.onNavigation();
      return result;
    };
  }

  private onNavigation(): void {
    // Defer slightly — SPA frameworks typically render after the route event fires.
    setTimeout(() => this.markDirty(true), 150);
  }

  private markDirty(force = false): void {
    this.dirty = true;
    if (this.scheduled !== null && !force) return;
    if (this.scheduled !== null) {
      window.clearTimeout(this.scheduled);
    }
    this.scheduled = window.setTimeout(() => {
      this.scheduled = null;
      this.refresh();
    }, 250);
  }

  private refresh(): void {
    const next = buildSnapshot();
    this.latest = next;
    this.dirty = false;

    const dropdownKey = next.openDropdown
      ? `${next.openDropdown.triggerSelector}|${next.openDropdown.options.length}`
      : null;
    const changed =
      next.route !== this.lastRoute ||
      dropdownKey !== this.lastDropdownKey ||
      next.focusedField?.selector !== this.latest?.focusedField?.selector;
    this.lastRoute = next.route;
    this.lastDropdownKey = dropdownKey;

    if (!changed && this.listeners.size === 0) return;
    for (const listener of this.listeners) listener(next);
  }
}
