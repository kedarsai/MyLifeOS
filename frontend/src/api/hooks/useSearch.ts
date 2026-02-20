import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../client";
import type { SearchResponse } from "../types";

interface SearchFilters {
  q: string;
  page?: number;
  page_size?: number;
  type?: string;
  tag?: string;
  goal?: string;
}

export function useSearch(filters: SearchFilters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== "") params.set(k, String(v));
  });
  return useQuery<SearchResponse>({
    queryKey: ["search", filters],
    queryFn: () => apiFetch(`/search?${params}`),
    enabled: filters.q.length > 0,
  });
}
