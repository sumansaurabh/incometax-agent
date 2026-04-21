export function fillField(selector: string, value: string): boolean {
  const el = document.querySelector<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(selector);
  if (!el) return false;
  if (el instanceof HTMLInputElement && el.type === "radio") {
    const radio = document.querySelector<HTMLInputElement>(`input[name='${el.name}'][value='${value}']`);
    if (!radio) {
      return false;
    }
    radio.checked = true;
    radio.dispatchEvent(new Event("input", { bubbles: true }));
    radio.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }
  if (el instanceof HTMLInputElement && el.type === "checkbox") {
    el.checked = value === "true" || value === "1" || value.toLowerCase() === "yes";
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }
  el.value = value;
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}
