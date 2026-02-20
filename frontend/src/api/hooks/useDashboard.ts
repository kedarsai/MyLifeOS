import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../client";
import type { DashboardSummary } from "../types";

export function useDashboard() {
  return useQuery<DashboardSummary>({
    queryKey: ["dashboard"],
    queryFn: () => apiFetch("/dashboard/summary"),
  });
}
