import { useEffect, useState } from "react";
import axios from "axios";
import api from "@/lib/api";

// custom hook to fetch data through the shared authenticated api client, so
// requests carry the Authorization header and the refresh-on-401 handling.
export function useDataFetch<T>(endpoint: string) {
  const [data, setData] = useState<T[]>([]);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    const fetchData = async () => {
      setLoading(true);
      try {
        // The api response interceptor unwraps response.data, so the resolved
        // value is the payload itself (cast to the shape TypeScript expects).
        const response = (await api.get<T[]>(endpoint)) as unknown as T[];
        if (active) setData(response);
      } catch (err) {
        if (active) {
          setError(
            axios.isAxiosError(err) ? err : new Error("An error occurred"),
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    };
    fetchData();
    return () => {
      active = false;
    };
  }, [endpoint]);

  return {
    data,
    loading,
    error,
  };
}