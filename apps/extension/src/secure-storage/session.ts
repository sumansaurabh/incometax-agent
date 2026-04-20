import { decryptForSession, encryptForSession } from "./crypto";

const KEY = "itx_encrypted_session";

export async function setSecureSession(value: string): Promise<void> {
  const encrypted = await encryptForSession(value);
  await chrome.storage.session.set({ [KEY]: encrypted });
}

export async function getSecureSession(): Promise<string | null> {
  const data = await chrome.storage.session.get(KEY);
  if (!data[KEY]) return null;
  return decryptForSession(data[KEY]);
}
