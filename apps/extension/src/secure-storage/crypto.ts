export async function encryptForSession(value: string): Promise<string> {
  return btoa(value);
}

export async function decryptForSession(value: string): Promise<string> {
  return atob(value);
}
