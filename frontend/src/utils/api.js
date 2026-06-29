// WHAT DOES THIS FILE DO: API helper functions for HTTP requests with auth and error handling

// ================== IMPORTS ==================
import { supabase } from '../supabaseClient';
// ================== IMPORTS ==================


// =========== VARIABLES : API configuration ===========
export const API_BASE = import.meta.env.VITE_API_BASE_URL || '';
// =========== VARIABLES : API configuration ===========


// =========== FUNCTIONS ===========

// ROLE: Retrieve admin secret from environment or local storage
function _adminSecret() {
  // Return admin secret for protected endpoint headers

  // FLOW-1: Check environment variable first, then local storage
  return import.meta.env.VITE_ADMIN_SECRET || localStorage.getItem('admin_secret') || '';
}


// ROLE: Make authenticated HTTP request to API with timeout and error handling
export async function apiFetch(path, options = {}) {
  // Fetch with auth header, admin headers if needed, and 30s timeout

  // FLOW-1: Get current session for auth token
  const { data: { session } } = await supabase.auth.getSession();

  // FLOW-2: Set up abort controller for 30-second timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);

  // FLOW-3: Build headers with cache control
  const headers = {
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'Expires': '0',
    ...options.headers,
  };

  // FLOW-4: Set content type if body provided but content type not set
  if (options.body && typeof options.body === 'string' && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  // FLOW-5: Add auth bearer token if session available
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`;
  }

  // FLOW-6: Add admin headers for protected endpoints
  if (path.startsWith('/api/admin') && !headers['X-Admin-User']) {
    headers['X-Admin-User'] = 'dashboard-admin';
  }

  // FLOW-7: Add admin secret to protected endpoints if available
  if (path.startsWith('/api/admin')) {
    const secret = _adminSecret();
    if (secret) headers['X-Admin-Secret'] = secret;
  }

  // FLOW-8: Make request with timeout signal
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    // FLOW-9: Parse response based on content type
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : { detail: await response.text() };

    // FLOW-10: Handle non-OK responses
    if (!response.ok) {
      // FLOW-11: Clear session on auth failures
      if (response.status === 401 || response.status === 403) {
        console.warn("Authentication failure (401/403) on API fetch. Clearing session.");
        try {
          supabase.auth.signOut();
        } catch (err) {
          // skip logout errors
        }
      }

      // FLOW-12: Extract error message and throw
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


// ROLE: Download file from API endpoint
export async function apiDownload(path, defaultFilename) {
  // Fetch file from API and trigger browser download

  // FLOW-1: Get current session for auth
  const { data: { session } } = await supabase.auth.getSession();

  // FLOW-2: Build headers with cache control
  const headers = {
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'Expires': '0',
  };

  // FLOW-3: Add auth if session available
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`;
  }

  // FLOW-4: Add admin headers if protected endpoint
  if (path.startsWith('/api/admin')) {
    headers['X-Admin-User'] = 'dashboard-admin';
    const secret = _adminSecret();
    if (secret) headers['X-Admin-Secret'] = secret;
  }

  // FLOW-5: Fetch blob from endpoint
  const response = await fetch(`${API_BASE}${path}`, { headers });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Download failed (${response.status})`);
  }

  // FLOW-6: Create blob URL and trigger download
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

// =========== FUNCTIONS ===========


