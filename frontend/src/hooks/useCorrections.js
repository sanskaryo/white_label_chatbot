import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../utils/api';

export function useCorrections() {
  const [corrections, setCorrections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchCorrections = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch('/api/admin/corrections?limit=100', {
        headers: { 'Content-Type': 'application/json', 'X-Admin-User': 'dashboard-admin' }
      });
      setCorrections(data.items || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCorrections();
  }, [fetchCorrections]);

  return { corrections, loading, error, refetch: fetchCorrections };
}
