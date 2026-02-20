import { Clock } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";

export default function RemindersPage() {
  return (
    <div>
      <PageHeader
        title="Reminders"
        description="Check-in reminders and backup status"
      />
      <EmptyState
        icon={Clock}
        title="Reminders"
        description="Reminder system is managed by the backend scheduler. Check back later for status updates."
      />
    </div>
  );
}
