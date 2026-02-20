import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../client";
import type { ThoughtArea, ThoughtTopic, TopicDetail, HeatmapCell } from "../types";

export function useAreas() {
  return useQuery<{ items: ThoughtArea[]; total: number }>({
    queryKey: ["thought-areas"],
    queryFn: () => apiFetch("/thoughts/areas"),
  });
}

export function useAreaTopics(areaId: string) {
  return useQuery<{ items: ThoughtTopic[]; total: number }>({
    queryKey: ["thought-topics", areaId],
    queryFn: () => apiFetch(`/thoughts/areas/${areaId}/topics`),
    enabled: !!areaId,
  });
}

export function useTopic(topicId: string) {
  return useQuery<TopicDetail>({
    queryKey: ["thought-topic", topicId],
    queryFn: () => apiFetch(`/thoughts/topics/${topicId}`),
    enabled: !!topicId,
  });
}

export function useHeatmap(months = 6) {
  return useQuery<{ items: HeatmapCell[] }>({
    queryKey: ["thought-heatmap", months],
    queryFn: () => apiFetch(`/thoughts/heatmap?months=${months}`),
  });
}
