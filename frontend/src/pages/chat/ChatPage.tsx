import { useState, useEffect, useRef } from "react";
import { MessageSquare, Plus, Send } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";
import { timeAgo } from "@/lib/formatters";
import { apiFetch } from "@/api/client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { ChatThread, ChatMessage } from "@/api/types";

function useThreads() {
  return useQuery<{ items: ChatThread[]; total: number }>({
    queryKey: ["chat-threads"],
    queryFn: () => apiFetch("/chat/threads"),
  });
}

function useMessages(threadId: string | null) {
  return useQuery<{ items: ChatMessage[]; total: number }>({
    queryKey: ["chat-messages", threadId],
    queryFn: () => apiFetch(`/chat/threads/${threadId}/messages`),
    enabled: !!threadId,
  });
}

export default function ChatPage() {
  const qc = useQueryClient();
  const { data: threads, isLoading } = useThreads();
  const [selectedThread, setSelectedThread] = useState<string | null>(null);
  const { data: messages } = useMessages(selectedThread);
  const [input, setInput] = useState("");
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
      // Trigger assistant reply
      void apiFetch(`/chat/threads/${selectedThread}/reply`, {
        method: "POST",
      }).then(() => {
        void qc.invalidateQueries({
          queryKey: ["chat-messages", selectedThread],
        });
      });
    },
  });

  const createThread = useMutation({
    mutationFn: (title: string) =>
      apiFetch<ChatThread>("/chat/threads", {
        method: "POST",
        body: JSON.stringify({ title }),
      }),
    onSuccess: (thread) => {
      void qc.invalidateQueries({ queryKey: ["chat-threads"] });
      setSelectedThread(thread.id);
      setCreating(false);
      setNewTitle("");
    },
  });

  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Chat" />

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
                key={thread.id}
                onClick={() => setSelectedThread(thread.id)}
                className={cn(
                  "text-left px-3 py-2 rounded-md text-[13px] transition-colors cursor-pointer",
                  selectedThread === thread.id
                    ? "bg-[var(--color-layer-active)] text-[var(--color-text-primary)]"
                    : "text-[var(--color-text-secondary)] hover:bg-[var(--color-layer-hover)]",
                )}
              >
                <div className="font-medium truncate">{thread.title}</div>
                <div className="text-[11px] text-[var(--color-text-tertiary)]">
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
                    key={msg.id}
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
                    </Card>
                  </div>
                ))}
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
                  className="flex-1 h-9 px-3 text-[13px] rounded-md bg-[var(--color-input-bg)] border border-[var(--color-input-border)] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-placeholder)] focus:outline-none focus:ring-2 focus:ring-[var(--color-input-focus-ring)] focus:border-transparent"
                />
                <Button
                  onClick={() => input.trim() && sendMessage.mutate(input.trim())}
                  loading={sendMessage.isPending}
                  disabled={!input.trim()}
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
