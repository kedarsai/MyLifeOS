import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../client";
import type { InsightCard } from "../types";

interface CardFilters {
  entity_type?: string;
  entity_id?: string;
  q?: string;
  limit?: number;
}

export function useCards(filters?: CardFilters) {
  const params = new URLSearchParams();
  if (filters?.entity_type) params.set("entity_type", filters.entity_type);
  if (filters?.entity_id) params.set("entity_id", filters.entity_id);
  if (filters?.q) params.set("q", filters.q);
  if (filters?.limit) params.set("limit", String(filters.limit));
  const qs = params.toString();
  return useQuery<{ items: InsightCard[]; total: number }>({
    queryKey: ["cards", filters],
    queryFn: () => apiFetch(`/cards${qs ? `?${qs}` : ""}`),
  });
}

export function useCard(cardId: string) {
  return useQuery<InsightCard>({
    queryKey: ["cards", cardId],
    queryFn: () => apiFetch(`/cards/${cardId}`),
    enabled: !!cardId,
  });
}
