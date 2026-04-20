export function readField(selector: string): string | null {
  const el = document.querySelector<HTMLInputElement | HTMLTextAreaElement>(selector);
  if (!el) return null;
  return el.value;
}
