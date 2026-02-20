import { useSearchParams } from "react-router-dom";
import { Select } from "@/components/ui/Select";
import { Input } from "@/components/ui/Input";
import { Toggle } from "@/components/ui/Toggle";
import { useGoals } from "@/api/hooks/useGoals";
import { useProjects } from "@/api/hooks/useProjects";
import { useDebounce } from "@/hooks/useDebounce";
import { useState, useEffect } from "react";

interface TaskFiltersValue {
  status?: string;
  goal_id?: string;
  project_id?: string;
  q?: string;
  include_done?: boolean;
}

interface TaskFiltersProps {
  value: TaskFiltersValue;
}

export function TaskFilters({ value }: TaskFiltersProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const { data: goalsData } = useGoals();
  const { data: projectsData } = useProjects();

  const [searchText, setSearchText] = useState(value.q ?? "");
  const debouncedSearch = useDebounce(searchText, 300);

  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    if (debouncedSearch) next.set("q", debouncedSearch);
    else next.delete("q");
    setSearchParams(next, { replace: true });
  }, [debouncedSearch]);

  const updateParam = (key: string, val: string) => {
    const next = new URLSearchParams(searchParams);
    if (val) next.set(key, val);
    else next.delete(key);
    setSearchParams(next, { replace: true });
  };

  const statusOptions = [
    { value: "open", label: "Open" },
    { value: "in_progress", label: "In Progress" },
    { value: "done", label: "Done" },
    { value: "cancelled", label: "Cancelled" },
  ];

  const goalOptions = (goalsData?.items ?? []).map((g) => ({
    value: g.goal_id,
    label: g.name,
  }));

  const projectOptions = (projectsData?.items ?? []).map((p) => ({
    value: p.id,
    label: p.name,
  }));

  return (
    <div className="flex flex-wrap items-end gap-3 mb-4">
      <div className="w-36">
        <Select
          options={statusOptions}
          placeholder="All statuses"
          value={value.status ?? ""}
          onChange={(e) => updateParam("status", e.target.value)}
        />
      </div>
      <div className="w-40">
        <Select
          options={goalOptions}
          placeholder="All goals"
          value={value.goal_id ?? ""}
          onChange={(e) => updateParam("goal_id", e.target.value)}
        />
      </div>
      <div className="w-40">
        <Select
          options={projectOptions}
          placeholder="All projects"
          value={value.project_id ?? ""}
          onChange={(e) => updateParam("project_id", e.target.value)}
        />
      </div>
      <div className="w-48">
        <Input
          placeholder="Search tasks..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
        />
      </div>
      <Toggle
        checked={value.include_done ?? false}
        onChange={(checked) => updateParam("include_done", checked ? "1" : "")}
        label="Show completed"
      />
    </div>
  );
}
