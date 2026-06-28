import { supabase } from '../supabaseClient';

export const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

/** Resolve the admin secret for protected admin endpoints. */
function _adminSecret() {
  return import.meta.env.VITE_ADMIN_SECRET || localStorage.getItem('admin_secret') || '';
}

export async function apiFetch(path, options = {}) {
  const { data: { session } } = await supabase.auth.getSession();
  
  // AbortController for a 30-second timeout to prevent permanent Loading... hang
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  
  const headers = {
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'Expires': '0',
    ...options.headers,
  };
  
  if (options.body && typeof options.body === 'string' && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`;
  }

  if (path.startsWith('/api/admin') && !headers['X-Admin-User']) {
    headers['X-Admin-User'] = 'dashboard-admin';
  }

  // Send admin secret for protected admin endpoints
  if (path.startsWith('/api/admin')) {
    const secret = _adminSecret();
    if (secret) headers['X-Admin-Secret'] = secret;
  }

  try {
    const response = await fetch(`${API_BASE}${path}`, { 
      ...options, 
      headers,
      signal: controller.signal
    });
    clearTimeout(timeoutId);
    
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : { detail: await response.text() };
    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        console.warn("Authentication failure (401/403) on API fetch. Clearing session.");
        try {
          supabase.auth.signOut();
        } catch (err) {
          // ignore sign out errors
        }
      }
      let message = payload?.detail || payload?.message || `Request failed (${response.status})`;
      if (typeof message === 'object') {
        message = JSON.stringify(message);
      }
      throw new Error(message);
    }
    return payload;
  } catch (error) {
    clearTimeout(timeoutId);
    throw error;
  }
}

export async function apiDownload(path, defaultFilename) {
  const { data: { session } } = await supabase.auth.getSession();
  
  const headers = {
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'Expires': '0',
  };
  
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`;
  }

  if (path.startsWith('/api/admin')) {
    headers['X-Admin-User'] = 'dashboard-admin';
    const secret = _adminSecret();
    if (secret) headers['X-Admin-Secret'] = secret;
  }

  const response = await fetch(`${API_BASE}${path}`, { headers });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Download failed (${response.status})`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = defaultFilename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}


