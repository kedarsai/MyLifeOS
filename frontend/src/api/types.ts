// --- Tasks (from routes_tasks.py) ---
export interface Task {
  task_id: string;
  logical_id: string;
  title: string;
  due_date: string | null;
  priority: "low" | "medium" | "high";
  status: "open" | "in_progress" | "done" | "cancelled";
  goal_id: string | null;
  goal_name: string | null;
  project_id: string | null;
  project_name: string | null;
  project_kind: string | null;
  rationale: string;
  updated_at: string;
}
export interface TasksResponse {
  items: Task[];
  total: number;
  filters: Record<string, string | number | boolean>;
}
export interface TodayResponse {
  today: string;
  due_today: Task[];
  overdue: Task[];
  next_actions: Task[];
}

// --- Goals (from routes_goals.py) ---
export interface Goal {
  goal_id: string;
  path: string;
  name: string;
  start_date: string;
  end_date: string | null;
  rules_md: string;
  metrics: string[];
  status: "active" | "paused" | "completed" | "archived";
  review_cadence_days: number;
  created_at: string;
  updated_at: string;
}
export interface GoalsResponse {
  items: Goal[];
  total: number;
}
export interface GoalDashboard {
  goal: Goal;
  metrics: {
    steps_avg_7d: number | null;
    step_streak_days: number;
    sleep_avg_min_7d: number | null;
    weight_trend_kg_30d: number | null;
    logging_completeness_7d_pct: number;
    linked_entries: number;
  };
  latest_review: {
    review_id: string;
    week_start: string;
    week_end: string;
    review: Record<string, unknown>;
    created_at: string;
  } | null;
}

// --- Entries (from routes_entries.py) ---
export interface Entry {
  id: string;
  path: string;
  created_at: string;
  updated_at: string;
  type: string;
  status: "inbox" | "processed" | "archived";
  summary: string;
  raw_text: string;
  tags: string[];
  goals: string[];
}
export interface InboxResponse {
  items: Entry[];
  total: number;
  limit: number;
  offset: number;
}
export interface TimelineResponse {
  items: Entry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
export interface CaptureResponse {
  entry_id: string;
  source_run_id: string;
  path: string;
  created: string;
}
export interface BatchCaptureResponse {
  count: number;
  items: CaptureResponse[];
}
export interface ProcessInboxResponse {
  selected_count: number;
  processed_count: number;
  processed_ids: string[];
  failed_count: number;
  failed_ids: string[];
  missing_paths: string[];
  run_ids: string[];
  observations_indexed: number;
  tasks_synced: number;
  improvements_created: number;
}

// --- Dashboard ---
export interface DashboardSummary {
  entries: {
    total: number;
    inbox: number;
    processed: number;
    archived: number;
  };
  runs: {
    total: number;
    pending: number;
    success: number;
    failed: number;
  };
  conflicts: { open: number };
  tasks_due_today: number;
  tasks_due: number;
  open_thoughts: number;
  recent_entries: Entry[];
  recent_runs: PromptRun[];
}

// --- Projects ---
export interface Project {
  id: string;
  name: string;
  kind: "client" | "personal" | "internal" | "other";
  status: "active" | "paused" | "completed" | "archived";
  notes: string;
  created_at: string;
  updated_at: string;
}

// --- Search ---
export interface SearchResponse {
  items: (Entry & { snippet?: string; score?: number })[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  facets: Record<string, Record<string, number>>;
}

// --- Chat ---
export interface ChatThread {
  thread_id: string;
  title: string;
  goal_id: string | null;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string;
  updated_at: string;
}
export interface ChatMessage {
  message_id: string;
  thread_id: string;
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  proposed_actions: ProposedAction[] | null;
  created_at: string;
}
export interface ProposedAction {
  action_type: string;
  label: string;
  params: Record<string, unknown>;
  requires_confirmation: boolean;
}

// --- Thought Areas & Topics ---
export interface ThoughtArea {
  area_id: string;
  name: string;
  description: string;
  topic_count: number;
  created_at: string;
  updated_at: string;
}
export interface ThoughtTopic {
  topic_id: string;
  area_id: string;
  name: string;
  description: string;
  entry_count: number;
  created_at: string;
  updated_at: string;
}
export interface TopicDetail extends ThoughtTopic {
  entries: { id: string; summary: string; type: string; created_at: string; tags: string[] }[];
}
export interface HeatmapCell {
  area_id: string;
  area_name: string;
  month: string;
  entry_count: number;
}

// --- Ideas ---
export type IdeaStatus = "raw" | "exploring" | "mature" | "converted" | "parked" | "dropped";
export interface Idea {
  idea_id: string;
  logical_id: string;
  title: string;
  description: string;
  status: IdeaStatus;
  converted_to_type: string | null;
  converted_to_id: string | null;
  source_entry_id: string | null;
  entry_count: number;
  version_no: number;
  created_at: string;
  updated_at: string;
}
export interface IdeaDetail extends Idea {
  entries: { id: string; summary: string; type: string; created_at: string; link_type: string; note: string }[];
}
export interface EntryDetail extends Entry {
  details_md: string;
  actions_md: string;
}
export interface IdeaConvertResult {
  idea: Idea;
  converted_to_type: string;
  converted_to_id: string;
}

// --- Insight Cards ---
export interface InsightCard {
  card_id: string;
  logical_id: string;
  entity_type: string;
  entity_id: string;
  source_thread_id: string | null;
  title: string;
  body_md: string;
  action_taken: string | null;
  tags: string[];
  version_no: number;
  created_at: string;
  updated_at: string;
}

// --- Improvements ---
export interface Improvement {
  improvement_id: string;
  title: string;
  rationale: string;
  source_entry_id: string | null;
  source_run_id: string;
  goal_id: string | null;
  status: "open" | "in_progress" | "adopted" | "dismissed";
  created_at: string;
  updated_at: string;
}

// --- Reviews ---
export interface Review {
  review_id: string;
  goal_id: string;
  week_start: string;
  week_end: string;
  review: Record<string, unknown>;
  created_at: string;
}

// --- Prompt Runs ---
export interface PromptRun {
  run_id: string;
  prompt_id: string;
  prompt_version: string;
  model: string | null;
  status: "pending" | "success" | "failed";
  created_at: string;
  parse_ok: boolean;
  error_text: string | null;
}

// --- Prompts ---
export interface PromptTemplate {
  prompt_id: string;
  version: string;
  template: string;
  schema_file: string | null;
  created_at: string;
}

// --- Conflicts ---
export interface Conflict {
  conflict_id: string;
  entity_type: string;
  entity_id: string;
  field: string;
  vault_value: string;
  app_value: string;
  status: "open" | "resolved";
  resolution: string | null;
  resolved_by: string | null;
  notes: string | null;
  created_at: string;
  resolved_at: string | null;
}
