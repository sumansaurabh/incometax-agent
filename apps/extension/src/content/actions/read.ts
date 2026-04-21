export function readField(selector: string): string | null {
  const el = document.querySelector<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(selector);
  if (!el) return null;
  if (el instanceof HTMLInputElement && el.type === "radio") {
    const checked = document.querySelector<HTMLInputElement>(`input[name='${el.name}']:checked`);
    return checked?.value ?? null;
  }
  if (el instanceof HTMLInputElement && el.type === "checkbox") {
    return el.checked ? "true" : "false";
  }
  return el.value;
}
