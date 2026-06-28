import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../utils/api';

export function useUploads() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch('/api/admin/workflow/summary', {
        headers: { 'Content-Type': 'application/json', 'X-Admin-User': 'dashboard-admin' }
      });
      setSummary(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  return { summary, loading, error, refetch: fetchSummary };
}
