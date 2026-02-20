import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../client";
import type { Project } from "../types";

export function useProjects(status?: string, kind?: string) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (kind) params.set("kind", kind);
  const qs = params.toString();
  return useQuery<{ items: Project[]; total: number }>({
    queryKey: ["projects", status, kind],
    queryFn: () => apiFetch(`/projects${qs ? `?${qs}` : ""}`),
  });
}

interface CreateProjectInput {
  name: string;
  kind?: string;
  status?: string;
  notes?: string;
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateProjectInput) =>
      apiFetch<Project>("/projects", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useUpdateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      data,
    }: {
      projectId: string;
      data: Partial<CreateProjectInput>;
    }) =>
      apiFetch<Project>(`/projects/${projectId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}
