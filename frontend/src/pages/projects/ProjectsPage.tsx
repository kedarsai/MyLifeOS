import { useState } from "react";
import { Settings, Plus } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { useProjects, useCreateProject } from "@/api/hooks/useProjects";
import { formatDate } from "@/lib/formatters";

const statusVariants: Record<string, "success" | "warning" | "default"> = {
  active: "success",
  paused: "warning",
  completed: "default",
  archived: "default",
};

export default function ProjectsPage() {
  const { data, isLoading, error } = useProjects();
  const createProject = useCreateProject();
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("personal");
  const [notes, setNotes] = useState("");

  const handleCreate = () => {
    createProject.mutate(
      { name, kind, notes },
      {
        onSuccess: () => {
          setCreateOpen(false);
          setName("");
          setNotes("");
        },
      },
    );
  };

  return (
    <div>
      <PageHeader
        title="Projects"
        actions={
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-3.5 w-3.5" />
            New Project
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
          Failed to load projects: {error.message}
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState
          icon={Settings}
          title="No projects yet"
          description="Create your first project."
          action={
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              Create Project
            </Button>
          }
        />
      )}

      {data && data.items.length > 0 && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
          {data.items.map((project) => (
            <Card key={project.id} className="p-4">
              <div className="flex items-start justify-between mb-2">
                <h3 className="text-[14px] font-semibold text-[var(--color-text-primary)]">
                  {project.name}
                </h3>
                <Badge variant={statusVariants[project.status] ?? "default"}>
                  {project.status}
                </Badge>
              </div>
              <Badge variant="outline" className="mb-2">
                {project.kind}
              </Badge>
              {project.notes && (
                <p className="text-[12px] text-[var(--color-text-secondary)] mt-2 line-clamp-2">
                  {project.notes}
                </p>
              )}
              <p className="text-[11px] text-[var(--color-text-tertiary)] mt-2">
                Created {formatDate(project.created_at)}
              </p>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create Project"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              loading={createProject.isPending}
              disabled={!name.trim()}
            >
              Create
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Input
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Project name"
          />
          <Select
            label="Kind"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            options={[
              { value: "personal", label: "Personal" },
              { value: "client", label: "Client" },
              { value: "internal", label: "Internal" },
              { value: "other", label: "Other" },
            ]}
          />
          <Textarea
            label="Notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optional notes..."
          />
        </div>
      </Modal>
    </div>
  );
}
