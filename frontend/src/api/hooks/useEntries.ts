import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../client";
import type {
  InboxResponse,
  TimelineResponse,
  CaptureResponse,
  BatchCaptureResponse,
  ProcessInboxResponse,
} from "../types";

export function useInbox(limit = 50, offset = 0) {
  return useQuery<InboxResponse>({
    queryKey: ["inbox", limit, offset],
    queryFn: () => apiFetch(`/entries/inbox?limit=${limit}&offset=${offset}`),
  });
}

interface TimelineFilters {
  page?: number;
  page_size?: number;
  type?: string;
  tag?: string;
  goal?: string;
  date_from?: string;
  date_to?: string;
}

export function useTimeline(filters: TimelineFilters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== "") params.set(k, String(v));
  });
  return useQuery<TimelineResponse>({
    queryKey: ["timeline", filters],
    queryFn: () => apiFetch(`/entries/timeline?${params}`),
  });
}

interface CaptureInput {
  raw_text: string;
  type?: string;
  tags?: string[];
  goals?: string[];
}

export function useCapture() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CaptureInput) =>
      apiFetch<CaptureResponse>("/entries/capture", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["inbox"] });
      void qc.invalidateQueries({ queryKey: ["timeline"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useBatchCapture() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CaptureInput) =>
      apiFetch<BatchCaptureResponse>("/entries/capture/batch", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["inbox"] });
      void qc.invalidateQueries({ queryKey: ["timeline"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useProcessInbox() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (entryIds?: string[]) =>
      apiFetch<ProcessInboxResponse>("/entries/process-inbox", {
        method: "POST",
        body: JSON.stringify(entryIds ? { entry_ids: entryIds } : {}),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["inbox"] });
      void qc.invalidateQueries({ queryKey: ["timeline"] });
      void qc.invalidateQueries({ queryKey: ["tasks"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
