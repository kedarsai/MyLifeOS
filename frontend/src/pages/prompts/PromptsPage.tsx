import { useState, useEffect } from "react";
import { Zap, Save, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn } from "@/lib/cn";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import type { PromptTemplate } from "@/api/types";

interface PromptFileItem {
  file: string;
  prompt_id: string;
  version: string;
}

export default function PromptsPage() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery<{
    items: PromptTemplate[];
    total: number;
  }>({
    queryKey: ["prompts"],
    queryFn: () => apiFetch("/prompts"),
  });

  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [editorContent, setEditorContent] = useState("");

  const { data: editorData } = useQuery<{
    files: PromptFileItem[];
    file?: string;
    content?: string;
  }>({
    queryKey: ["prompts-editor", selectedFile],
    queryFn: () =>
      apiFetch(
        `/prompts/editor${selectedFile ? `?file=${encodeURIComponent(selectedFile)}` : ""}`,
      ),
  });

  // Sync editor content when editorData changes for the selected file
  useEffect(() => {
    if (editorData?.content && selectedFile) {
      setEditorContent(editorData.content);
    }
  }, [editorData?.content, selectedFile]);

  const loadFile = (file: string) => {
    setSelectedFile(file);
    setEditorContent("");
  };

  const saveFile = useMutation({
    mutationFn: () =>
      apiFetch("/prompts/editor", {
        method: "POST",
        body: JSON.stringify({
          file: selectedFile,
          content: editorContent,
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["prompts"] });
    },
  });

  const reloadPrompts = useMutation({
    mutationFn: () => apiFetch("/prompts/reload", { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["prompts"] });
    },
  });

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        title="Prompts"
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => reloadPrompts.mutate()}
            loading={reloadPrompts.isPending}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Reload
          </Button>
        }
      />

      {isLoading && (
        <div className="flex justify-center py-12">
          <Spinner size="lg" />
        </div>
      )}

      {error && (
        <div className="text-[13px] text-[var(--color-danger)] py-4">
          Failed to load prompts: {(error as Error).message}
        </div>
      )}

      {data && (
        <div className="flex flex-1 gap-4 min-h-0">
          {/* Prompt list */}
          <div className="w-64 shrink-0 overflow-y-auto scrollbar">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)] mb-2 px-2">
              Files ({editorData?.files?.length ?? 0})
            </div>
            <div className="flex flex-col gap-0.5">
              {editorData?.files?.map((item) => (
                <button
                  key={item.file}
                  onClick={() => loadFile(item.file)}
                  className={cn(
                    "text-left px-2 py-1.5 rounded-md text-[13px] transition-colors cursor-pointer",
                    selectedFile === item.file
                      ? "bg-[var(--color-layer-active)] text-[var(--color-text-primary)]"
                      : "text-[var(--color-text-secondary)] hover:bg-[var(--color-layer-hover)]",
                  )}
                >
                  <div className="truncate">{item.file}</div>
                  <div className="text-[11px] text-[var(--color-text-tertiary)]">
                    {item.prompt_id}{" "}
                    <span className="opacity-50">v{item.version}</span>
                  </div>
                </button>
              ))}
            </div>

            <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)] mt-4 mb-2 px-2">
              Templates ({data.total})
            </div>
            <div className="flex flex-col gap-0.5">
              {data.items.map((tpl) => (
                <div
                  key={tpl.prompt_id}
                  className="px-2 py-1 text-[12px] text-[var(--color-text-tertiary)]"
                >
                  {tpl.prompt_id}{" "}
                  <span className="opacity-50">v{tpl.version}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Editor */}
          <div className="flex-1 flex flex-col min-w-0">
            {!selectedFile ? (
              <EmptyState
                icon={Zap}
                title="Select a prompt file"
                description="Choose a YAML file from the list to edit."
              />
            ) : (
              <>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[13px] font-medium text-[var(--color-text-primary)]">
                    {selectedFile}
                  </span>
                  <Button
                    size="sm"
                    onClick={() => saveFile.mutate()}
                    loading={saveFile.isPending}
                  >
                    <Save className="h-3.5 w-3.5" />
                    Save
                  </Button>
                </div>
                <textarea
                  value={editorContent}
                  onChange={(e) => setEditorContent(e.target.value)}
                  className="flex-1 min-h-[400px] p-3 text-[13px] font-mono rounded-md bg-[var(--color-input-bg)] border border-[var(--color-input-border)] text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-input-focus-ring)] focus:border-transparent resize-none"
                  spellCheck={false}
                />
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
