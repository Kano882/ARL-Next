export async function fetchAuthenticatedBlob(path, { signal } = {}) {
  const url = new URL(path, window.location.origin);
  if (url.origin !== window.location.origin || !url.pathname.startsWith('/api/')) {
    throw new Error('Invalid authenticated resource URL');
  }
  const token = localStorage.getItem('token') || '';
  const response = await fetch(url.href, {
    headers: token ? { Token: token } : {}, signal, redirect: 'error', cache: 'no-store',
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  if ((response.headers.get('content-type') || '').includes('application/json')) {
    const data = await response.json();
    throw new Error(data.message || 'Invalid file response');
  }
  return response.blob();
}

export async function downloadAuthenticated(path, filename) {
  const blob = await fetchAuthenticatedBlob(path);
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
