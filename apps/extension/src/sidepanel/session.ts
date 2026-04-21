const THREAD_KEY = "itx_sidepanel_thread_id";
const USER_KEY = "itx_sidepanel_user_id";

export type SidepanelSession = {
  threadId: string;
  userId: string;
};

export async function loadSidepanelSession(): Promise<SidepanelSession | null> {
  const stored = await chrome.storage.session.get([THREAD_KEY, USER_KEY]);
  const threadId = stored[THREAD_KEY];
  const userId = stored[USER_KEY];
  if (!threadId || !userId) {
    return null;
  }
  return { threadId, userId };
}

export async function saveSidepanelSession(session: SidepanelSession): Promise<void> {
  await chrome.storage.session.set({
    [THREAD_KEY]: session.threadId,
    [USER_KEY]: session.userId,
  });
}

export async function clearSidepanelSession(): Promise<void> {
  await chrome.storage.session.remove([THREAD_KEY, USER_KEY]);
}

export function createSidepanelUserId(): string {
  return `extension-${crypto.randomUUID()}`;
}