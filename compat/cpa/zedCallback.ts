export function validateZedCallback(input: string, state?: string): boolean {
  if (!state || !/^[a-f0-9]{48}$/.test(state) || input.length > 8192) return false;
  let url: URL;
  try {
    url = new URL(input.trim());
  } catch {
    return false;
  }
  return (
    url.protocol === 'http:' &&
    url.hostname === '127.0.0.1' &&
    Boolean(url.port) &&
    !url.username && !url.password &&
    url.pathname === '/' && !url.hash &&
    url.searchParams.getAll('user_id').length === 1 &&
    Boolean(url.searchParams.get('user_id')?.trim()) &&
    url.searchParams.getAll('access_token').length === 1 &&
    Boolean(url.searchParams.get('access_token'))
  );
}
