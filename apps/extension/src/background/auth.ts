const TOKEN_KEY = "itx_auth_token";

export async function setAuthToken(token: string): Promise<void> {
  await chrome.storage.session.set({ [TOKEN_KEY]: token });
}

export async function getAuthToken(): Promise<string | null> {
  const data = await chrome.storage.session.get(TOKEN_KEY);
  return data[TOKEN_KEY] ?? null;
}
