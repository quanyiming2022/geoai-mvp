// Decoding is only a refresh scheduling hint. FastAPI/Auth verify identity separately.
export function needsRefresh(token, now = Date.now()) {
  if (!token) return true;
  try {
    const part = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const { exp } = JSON.parse(atob(part));
    return !Number.isFinite(exp) || exp * 1000 <= now + 60000;
  } catch { return true; }
}
