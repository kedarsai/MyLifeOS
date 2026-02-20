import { useState, useEffect, useRef } from "react";
import { MessageSquare, Plus, Send, CheckCircle, Loader2 } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";
import { timeAgo } from "@/lib/formatters";
import { apiFetch } from "@/api/client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { ChatThread, ChatMessage, ProposedAction } from "@/api/types";

function useThreads(entityType?: string, entityId?: string) {
  const params = new URLSearchParams();
  if (entityType) params.set("entity_type", entityType);
  if (entityId) params.set("entity_id", entityId);
  const qs = params.toString();
  return useQuery<{ items: ChatThread[]; total: number }>({
    queryKey: ["chat-threads", entityType, entityId],
    queryFn: () => apiFetch(`/chat/threads${qs ? `?${qs}` : ""}`),
  });
}

function useMessages(threadId: string | null) {
  return useQuery<{ items: ChatMessage[]; total: number }>({
    queryKey: ["chat-messages", threadId],
    queryFn: () => apiFetch(`/chat/threads/${threadId}/messages`),
    enabled: !!threadId,
  });
}

function ProposedActionButtons({
  threadId,
  actions,
}: {
  threadId: string;
  actions: ProposedAction[];
}) {
  const qc = useQueryClient();
  const [executing, setExecuting] = useState<string | null>(null);
  const [executed, setExecuted] = useState<Set<string>>(new Set());

  const handleConfirm = async (action: ProposedAction) => {
    const key = `${action.action_type}:${action.label}`;
    setExecuting(key);
    try {
      await apiFetch(`/chat/threads/${threadId}/confirm-action`, {
        method: "POST",
        body: JSON.stringify({
          action_type: action.action_type,
          label: action.label,
          params: action.params,
        }),
      });
      setExecuted((prev) => new Set(prev).add(key));
      void qc.invalidateQueries({ queryKey: ["tasks"] });
      void qc.invalidateQueries({ queryKey: ["ideas"] });
      void qc.invalidateQueries({ queryKey: ["cards"] });
    } catch {
      // Silently fail
    } finally {
      setExecuting(null);
    }
  };

  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {actions.map((action) => {
        const key = `${action.action_type}:${action.label}`;
        const done = executed.has(key);
        return (
          <Button
            key={key}
            variant={done ? "ghost" : "secondary"}
            size="sm"
            onClick={() => !done && handleConfirm(action)}
            loading={executing === key}
            disabled={done}
          >
            {done && <CheckCircle className="h-3 w-3 mr-1" />}
            {action.label}
          </Button>
        );
      })}
    </div>
  );
}

export default function ChatPage() {
  const [searchParams] = useSearchParams();
  const entityType = searchParams.get("entity_type") || undefined;
  const entityId = searchParams.get("entity_id") || undefined;

  const qc = useQueryClient();
  const { data: threads, isLoading } = useThreads(entityType, entityId);
  const [selectedThread, setSelectedThread] = useState<string | null>(null);
  const { data: messages } = useMessages(selectedThread);
  const [input, setInput] = useState("");
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [isReplying, setIsReplying] = useState(false);
  const [replyError, setReplyError] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isReplying]);

  const sendMessage = useMutation({
    mutationFn: (content: string) =>
      apiFetch(`/chat/threads/${selectedThread}/messages`, {
        method: "POST",
        body: JSON.stringify({ role: "user", content }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ["chat-messages", selectedThread],
      });
      setInput("");
      setIsReplying(true);
      setReplyError(false);
      // Trigger assistant reply
      void apiFetch(`/chat/threads/${selectedThread}/reply`, {
        method: "POST",
      })
        .then(() => {
          void qc.invalidateQueries({
            queryKey: ["chat-messages", selectedThread],
          });
        })
        .catch(() => {
          setReplyError(true);
        })
        .finally(() => {
          setIsReplying(false);
        });
    },
  });

  const createThread = useMutation({
    mutationFn: (title: string) =>
      apiFetch<ChatThread>("/chat/threads", {
        method: "POST",
        body: JSON.stringify({
          title,
          entity_type: entityType || null,
          entity_id: entityId || null,
        }),
      }),
    onSuccess: (thread) => {
      void qc.invalidateQueries({ queryKey: ["chat-threads"] });
      setSelectedThread(thread.thread_id);
      setCreating(false);
      setNewTitle("");
    },
  });

  // Entity context banner
  const entityLabel =
    entityType === "thought_topic"
      ? "Topic"
      : entityType === "idea"
        ? "Idea"
        : entityType === "goal"
          ? "Goal"
          : null;

  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Chat" />

      {entityLabel && (
        <div className="mb-3 px-3 py-2 rounded-md bg-[var(--color-surface-secondary)] border border-[var(--color-border-subtle)] text-[12px] text-[var(--color-text-secondary)]">
          Context: <Badge variant="info">{entityLabel}</Badge>{" "}
          <span className="text-[var(--color-text-tertiary)]">{entityId}</span>
        </div>
      )}

      <div className="flex flex-1 min-h-0 gap-4">
        {/* Thread list */}
        <div className="w-[340px] shrink-0 flex flex-col">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[12px] font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider">
              Threads
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setCreating(true)}
            >
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </div>

          {creating && (
            <div className="flex gap-2 mb-2">
              <Input
                placeholder="Thread title..."
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                className="flex-1"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && newTitle.trim()) {
                    createThread.mutate(newTitle.trim());
                  }
                }}
                autoFocus
              />
            </div>
          )}

          {isLoading && <Spinner />}

          <div className="flex flex-col gap-1 overflow-y-auto scrollbar flex-1">
            {threads?.items.map((thread) => (
              <button
                key={thread.thread_id}
                onClick={() => setSelectedThread(thread.thread_id)}
                className={cn(
                  "text-left px-3 py-2 rounded-md text-[13px] transition-colors cursor-pointer",
                  selectedThread === thread.thread_id
                    ? "bg-[var(--color-layer-active)] text-[var(--color-text-primary)]"
                    : "text-[var(--color-text-secondary)] hover:bg-[var(--color-layer-hover)]",
                )}
              >
                <div className="font-medium truncate">{thread.title}</div>
                <div className="flex items-center gap-1.5 text-[11px] text-[var(--color-text-tertiary)]">
                  {thread.entity_type && (
                    <Badge variant="outline">{thread.entity_type}</Badge>
                  )}
                  {timeAgo(thread.updated_at)}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Message area */}
        <div className="flex-1 flex flex-col min-w-0">
          {!selectedThread ? (
            <EmptyState
              icon={MessageSquare}
              title="Select a thread"
              description="Choose or create a conversation thread."
            />
          ) : (
            <>
              <div className="flex-1 overflow-y-auto scrollbar px-2 py-4">
                {messages?.items.map((msg) => (
                  <div
                    key={msg.message_id}
                    className={cn(
                      "mb-3 max-w-[80%]",
                      msg.role === "user" ? "ml-auto" : "mr-auto",
                    )}
                  >
                    <Card
                      className={cn(
                        "px-3 py-2",
                        msg.role === "user"
                          ? "bg-[var(--color-accent-muted)]"
                          : "",
                      )}
                    >
                      <div className="text-[11px] text-[var(--color-text-tertiary)] mb-1">
                        {msg.role}
                      </div>
                      <div className="text-[13px] text-[var(--color-text-primary)] whitespace-pre-wrap">
                        {msg.content}
                      </div>
                      {msg.proposed_actions && msg.proposed_actions.length > 0 && selectedThread && (
                        <ProposedActionButtons
                          threadId={selectedThread}
                          actions={msg.proposed_actions}
                        />
                      )}
                    </Card>
                  </div>
                ))}
                {/* Thinking indicator */}
                {isReplying && (
                  <div className="mb-3 max-w-[80%] mr-auto">
                    <Card className="px-3 py-2">
                      <div className="flex items-center gap-2 text-[13px] text-[var(--color-text-tertiary)]">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Thinking...</span>
                      </div>
                    </Card>
                  </div>
                )}

                {/* Reply error */}
                {replyError && !isReplying && (
                  <div className="mb-3 max-w-[80%] mr-auto">
                    <Card className="px-3 py-2 border-[var(--color-status-danger)]">
                      <div className="text-[13px] text-[var(--color-status-danger)]">
                        Failed to get a reply. Check your API key or try again.
                      </div>
                    </Card>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
              <div className="flex gap-2 pt-3 border-t border-[var(--color-border-subtle)]">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey && input.trim()) {
                      e.preventDefault();
                      sendMessage.mutate(input.trim());
                    }
                  }}
                  placeholder="Type a message..."
                  disabled={isReplying}
                  className="flex-1 h-9 px-3 text-[13px] rounded-md bg-[var(--color-input-bg)] border border-[var(--color-input-border)] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-placeholder)] focus:outline-none focus:ring-2 focus:ring-[var(--color-input-focus-ring)] focus:border-transparent disabled:opacity-50"
                />
                <Button
                  onClick={() => input.trim() && sendMessage.mutate(input.trim())}
                  loading={sendMessage.isPending}
                  disabled={!input.trim() || isReplying}
                >
                  <Send className="h-3.5 w-3.5" />
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
