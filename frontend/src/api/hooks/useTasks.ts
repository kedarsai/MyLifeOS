import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../client";
import type { TasksResponse, TodayResponse } from "../types";

interface TaskFilters {
  status?: string;
  goal_id?: string;
  project_id?: string;
  q?: string;
  include_done?: boolean;
  limit?: number;
}

export function useTasks(filters: TaskFilters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== "") params.set(k, String(v));
  });
  return useQuery<TasksResponse>({
    queryKey: ["tasks", filters],
    queryFn: () => apiFetch(`/tasks?${params}`),
  });
}

export function useToday() {
  return useQuery<TodayResponse>({
    queryKey: ["today"],
    queryFn: () => apiFetch("/today"),
  });
}

export function useCompleteTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/tasks/${id}/complete`, { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tasks"] });
      void qc.invalidateQueries({ queryKey: ["today"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useDeleteTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/tasks/${id}/delete`, { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tasks"] });
      void qc.invalidateQueries({ queryKey: ["today"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useAssignTaskProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      taskId,
      projectId,
    }: {
      taskId: string;
      projectId: string | null;
    }) =>
      apiFetch(`/tasks/${taskId}/project`, {
        method: "POST",
        body: JSON.stringify({ project_id: projectId }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}
