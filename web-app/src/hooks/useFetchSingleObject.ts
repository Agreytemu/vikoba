import { useEffect, useState } from "react";
import api from "@/lib/api";

export function useFetchSingleObject<T>(
  endpoint: string,
  editItem: boolean = false
) {
  const [data, setData] = useState<T>();

  useEffect(() => {
    let active = true;
    const fetchData = async () => {
      try {
        // The api response interceptor unwraps response.data, so the resolved
        // value is the payload itself (cast to the shape TypeScript expects).
        const response = (await api.get<T>(endpoint)) as unknown as T;
        if (active) setData(response);
      } catch {
        // Swallow: the caller decides how to surface a failure.
      }
    };
    if (editItem === true) {
      fetchData();
    }
    return () => {
      active = false;
    };
  }, [endpoint, editItem]);
  return {
    data,
  };
}