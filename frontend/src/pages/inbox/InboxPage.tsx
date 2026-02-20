import { useState } from "react";
import { Inbox, Zap } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { Card } from "@/components/ui/Card";
import { InboxItem } from "./InboxItem";
import { useInbox, useProcessInbox } from "@/api/hooks/useEntries";
import type { ProcessInboxResponse } from "@/api/types";

const LIMIT = 20;

export default function InboxPage() {
  const [offset, setOffset] = useState(0);
  const { data, isLoading, error } = useInbox(LIMIT, offset);
  const processInbox = useProcessInbox();
  const [processResult, setProcessResult] =
    useState<ProcessInboxResponse | null>(null);

  const handleProcessAll = () => {
    processInbox.mutate(undefined, {
      onSuccess: (result) => setProcessResult(result),
    });
  };

  return (
    <div>
      <PageHeader
        title="Inbox"
        description={
          data ? `${data.total} item${data.total !== 1 ? "s" : ""}` : undefined
        }
        actions={
          <Button
            size="sm"
            onClick={handleProcessAll}
            loading={processInbox.isPending}
            disabled={!data || data.total === 0}
          >
            <Zap className="h-3.5 w-3.5" />
            Process All
          </Button>
        }
      />

      {/* Process result summary */}
      {processResult && (
        <Card className="p-4 mb-4 border-[var(--color-success-muted-border)] bg-[var(--color-success-muted)]">
          <p className="text-[13px] font-medium text-[var(--color-success)] mb-1">
            Processing complete
          </p>
          <div className="text-[12px] text-[var(--color-text-secondary)] space-y-0.5">
            <p>
              {processResult.processed_count} processed,{" "}
              {processResult.failed_count} failed
            </p>
            {processResult.tasks_synced > 0 && (
              <p>{processResult.tasks_synced} tasks synced</p>
            )}
            {processResult.improvements_created > 0 && (
              <p>{processResult.improvements_created} improvements created</p>
            )}
          </div>
        </Card>
      )}

      {isLoading && (
        <div className="flex justify-center py-12">
          <Spinner size="lg" />
        </div>
      )}

      {error && (
        <div className="text-[13px] text-[var(--color-danger)] py-4">
          Failed to load inbox: {error.message}
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState
          icon={Inbox}
          title="Inbox empty"
          description="All entries have been processed. Capture something new!"
        />
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="flex flex-col gap-3">
            {data.items.map((entry) => (
              <InboxItem key={entry.id} entry={entry} />
            ))}
          </div>

          {data.total > offset + LIMIT && (
            <div className="mt-4 flex justify-center">
              <Button
                variant="secondary"
                onClick={() => setOffset((o) => o + LIMIT)}
              >
                Load more
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
