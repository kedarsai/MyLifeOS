import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../client";
import type { Idea, IdeaDetail, IdeaConvertResult } from "../types";

export function useIdeas(status?: string) {
  const params = status ? `?status=${status}` : "";
  return useQuery<{ items: Idea[]; total: number }>({
    queryKey: ["ideas", status],
    queryFn: () => apiFetch(`/ideas${params}`),
  });
}

export function useIdea(ideaId: string) {
  return useQuery<IdeaDetail>({
    queryKey: ["ideas", ideaId],
    queryFn: () => apiFetch(`/ideas/${ideaId}`),
    enabled: !!ideaId,
  });
}

export function useCreateIdea() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { title: string; description?: string }) =>
      apiFetch<Idea>("/ideas", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["ideas"] });
    },
  });
}

export function useUpdateIdea() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      ideaId,
      data,
    }: {
      ideaId: string;
      data: { title?: string; description?: string; status?: string };
    }) =>
      apiFetch<Idea>(`/ideas/${ideaId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["ideas"] });
    },
  });
}

export function useConvertIdea() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      ideaId,
      targetType,
      extra,
    }: {
      ideaId: string;
      targetType: string;
      extra?: Record<string, string>;
    }) =>
      apiFetch<IdeaConvertResult>(`/ideas/${ideaId}/convert`, {
        method: "POST",
        body: JSON.stringify({ target_type: targetType, ...extra }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["ideas"] });
      void qc.invalidateQueries({ queryKey: ["goals"] });
      void qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}
