import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../utils/api';

export function useAdminMetrics() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchMetrics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [analyticsData, langfuseData] = await Promise.all([
        apiFetch('/api/admin/analytics/summary', {
          headers: { 'Content-Type': 'application/json', 'X-Admin-User': 'dashboard-admin' }
        }),
        apiFetch('/api/admin/metrics/langfuse', {
          headers: { 'Content-Type': 'application/json', 'X-Admin-User': 'dashboard-admin' }
        }).catch(e => ({ error: e.message }))
      ]);

      setMetrics({
        ...analyticsData,
        langfuse: langfuseData
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  return { metrics, loading, error, refetch: fetchMetrics };
}
