import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../client";
import type { Goal, GoalsResponse, GoalDashboard } from "../types";

export function useGoals(status?: string) {
  const params = status ? `?status=${status}` : "";
  return useQuery<GoalsResponse>({
    queryKey: ["goals", status],
    queryFn: () => apiFetch(`/goals${params}`),
  });
}

export function useGoal(goalId: string) {
  return useQuery<Goal>({
    queryKey: ["goals", goalId],
    queryFn: () => apiFetch(`/goals/${goalId}`),
    enabled: !!goalId,
  });
}

export function useGoalDashboard(goalId: string) {
  return useQuery<GoalDashboard>({
    queryKey: ["goals", goalId, "dashboard"],
    queryFn: () => apiFetch(`/goals/${goalId}/dashboard`),
    enabled: !!goalId,
  });
}

interface CreateGoalInput {
  name: string;
  start_date: string;
  end_date?: string | null;
  rules_md?: string;
  metrics?: string[];
  status?: string;
  review_cadence_days?: number;
}

export function useCreateGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateGoalInput) =>
      apiFetch<Goal>("/goals", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["goals"] });
    },
  });
}

export function useUpdateGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      goalId,
      data,
    }: {
      goalId: string;
      data: Partial<CreateGoalInput>;
    }) =>
      apiFetch<Goal>(`/goals/${goalId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["goals"] });
    },
  });
}
