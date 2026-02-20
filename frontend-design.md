# Frontend Design System

A comprehensive design system reference extracted from the LifeOS project. Use this document to reproduce the same UI consistency, information density, and visual quality in new projects.

**Inspired by:** [Plane](https://plane.so) (project management), Linear, Notion — information-dense, tool-like UIs that feel like native apps.

---

## 1. Stack & Tooling

| Layer | Choice | Why |
|-------|--------|-----|
| Framework | **React 19** + TypeScript | Component model, ecosystem |
| Build | **Vite** | Fast HMR, clean config |
| Styling | **TailwindCSS v4** + CSS custom properties | Utility-first + themeable tokens |
| Data fetching | **TanStack React Query** | Cache, mutations, invalidation |
| Routing | **React Router v7** | Standard SPA routing |
| Icons | **Lucide React** | Consistent 24x24 SVG icons, tree-shakeable |
| Font | **Inter Variable** (via `@fontsource-variable/inter`) | Optimized variable font, no Google Fonts CDN |
| Classname merge | `clsx` (no `tailwind-merge` needed) | Simple, fast |

### Key architectural decisions

- **No CSS-in-JS, no styled-components** — all styling via Tailwind utilities + CSS custom properties
- **No component library** (no shadcn, no Radix, no MUI) — every component is hand-built and weighs < 100 lines
- **No state management library** — React Query handles server state; `useState` handles local UI state
- **Dark mode is first-class** — not an afterthought. Every color is a CSS variable that swaps via `.dark` class

---

## 2. Design Tokens (CSS Custom Properties)

All colors, radii, and shadows are defined as CSS custom properties in `index.css` under `@theme` (Tailwind v4) and `:root` / `.dark` blocks. **Never use raw hex values in components** — always reference tokens.

### 2.1 Color Architecture

The color system uses a **depth model** with three layers:

```
Canvas  →  Surface  →  Layer
(background)  (cards/panels)  (hover/active states)
```

#### Light theme

```css
:root {
  /* Canvas: deepest background, used once on <body> */
  --color-canvas: #f7f7f8;

  /* Surface: cards, panels, sidebar backgrounds */
  --color-surface-primary: #ffffff;
  --color-surface-secondary: #f9fafb;
  --color-surface-tertiary: #f3f4f6;

  /* Layer: interactive states within surfaces */
  --color-layer-hover: #f3f4f6;
  --color-layer-active: #e5e7eb;
  --color-layer-selected: #eff6ff;
}
```

#### Dark theme

```css
.dark {
  --color-canvas: #0a0a0b;
  --color-surface-primary: #111113;
  --color-surface-secondary: #18181b;
  --color-surface-tertiary: #1f1f23;

  --color-layer-hover: #27272a;
  --color-layer-active: #3f3f46;
  --color-layer-selected: #1e3a5f;
}
```

#### Text hierarchy (4 levels)

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--color-text-primary` | `#111827` | `#fafafa` | Headings, body text, primary content |
| `--color-text-secondary` | `#4b5563` | `#a1a1aa` | Descriptions, supporting text |
| `--color-text-tertiary` | `#9ca3af` | `#71717a` | Timestamps, labels, metadata |
| `--color-text-placeholder` | `#d1d5db` | `#52525b` | Input placeholders, empty states |

#### Borders (3 weights)

| Token | Usage |
|-------|-------|
| `--color-border-subtle` | Card borders, section dividers (barely visible) |
| `--color-border-default` | Input borders, table borders |
| `--color-border-strong` | Scrollbar thumb hover, emphasis borders |

#### Accent (blue)

```css
--color-accent: #2563eb;        /* Primary buttons, links, focus rings */
--color-accent-hover: #1d4ed8;  /* Button hover state */
--color-accent-muted: #eff6ff;  /* Selected row backgrounds */
```

#### Status colors (4 semantic colors)

Each has three variants: solid, muted background, and muted border:

```css
/* Success (green) */
--color-success: #059669;
--color-success-muted: #ecfdf5;
--color-success-muted-border: #a7f3d0;

/* Warning (amber) */
--color-warning: #d97706;
--color-warning-muted: #fffbeb;
--color-warning-muted-border: #fde68a;

/* Danger (red) */
--color-danger: #dc2626;
--color-danger-muted: #fef2f2;
--color-danger-muted-border: #fecaca;

/* Info (blue) */
--color-info: #2563eb;
--color-info-muted: #eff6ff;
--color-info-muted-border: #bfdbfe;
```

In dark mode, muted backgrounds use `rgba()` with 12% opacity, and borders use 25% opacity — this creates subtle tints that work on dark surfaces.

#### Sidebar (always dark)

The sidebar uses its own color subsystem that stays dark in both light and dark themes:

```css
--color-sidebar-bg: #111827;
--color-sidebar-bg-hover: rgba(255,255,255,0.06);
--color-sidebar-bg-active: rgba(255,255,255,0.10);
--color-sidebar-text: #d1d5db;
--color-sidebar-text-active: #ffffff;
--color-sidebar-text-muted: #6b7280;
--color-sidebar-border: rgba(255,255,255,0.08);
--color-sidebar-section: #6b7280;
```

#### Input tokens

```css
--color-input-bg: #ffffff;          /* dark: #18181b */
--color-input-border: #d1d5db;      /* dark: #3f3f46 */
--color-input-focus-ring: #2563eb;  /* dark: #3b82f6 */
```

### 2.2 Border Radius

Tight, subtle radii — not rounded, not sharp:

```css
--radius-xs: 3px;     /* Tiny elements (kbd tags) */
--radius-sm: 4px;     /* Badges, small buttons */
--radius-md: 6px;     /* Default for inputs, buttons, cards */
--radius-lg: 8px;     /* Cards */
--radius-xl: 12px;    /* Modals, panels */
--radius-full: 9999px; /* Pills, badges */
```

### 2.3 Shadows

All shadows use **dark blue-grey** (`rgba(41, 47, 61, ...)`) — never pure black:

```css
--shadow-xs: 0 1px 2px rgba(41, 47, 61, 0.04);
--shadow-sm: 0 1px 3px rgba(41, 47, 61, 0.06);
--shadow-md: 0 2px 8px rgba(41, 47, 61, 0.08);
--shadow-lg: 0 4px 16px rgba(41, 47, 61, 0.10);
--shadow-xl: 0 8px 32px rgba(41, 47, 61, 0.12);
--shadow-overlay: 0 16px 48px rgba(41, 47, 61, 0.16);  /* Modals, dropdowns */
```

---

## 3. Typography

### 3.1 Base size & rendering

```css
html {
  font-size: 13px;  /* The entire app runs at 13px base — dense, tool-like */
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
}
body {
  font-family: var(--font-sans);  /* "Inter Variable", system-ui, -apple-system, sans-serif */
}
```

### 3.2 Type scale

| Size | Usage | Tailwind class |
|------|-------|----------------|
| **10px** | Keyboard shortcut hints (kbd) | `text-[10px]` |
| **11px** | Badges, timestamps, metadata, table headers, tertiary labels | `text-[11px]` |
| **12px** | Section headers (uppercase), secondary descriptions, status labels | `text-[12px]` |
| **13px** | **Body text** (default), inputs, buttons (md), table cells, card content | `text-[13px]` |
| **14px** | Command palette input | `text-[14px]` |
| **15px** | Page titles in header, modal titles, sidebar brand | `text-[15px]` |
| **text-lg** | PageHeader title (~18px) | `text-lg` |

### 3.3 Font weight conventions

| Weight | Usage |
|--------|-------|
| Normal (400) | Body text, descriptions, inputs |
| Medium (500) | Labels, section headers, nav items (active), badges |
| Semibold (600) | Page titles, card titles, modal titles, sidebar brand |
| Bold (700) | Sidebar "LifeOS" brand only |

### 3.4 Section header pattern

Uppercase, tracked-out, 11-12px, tertiary color:

```tsx
<h4 className="text-[12px] font-medium text-[var(--color-text-tertiary)] uppercase mb-2">
  Section Title
</h4>
```

For sidebar group headers, add `tracking-widest` and `font-semibold`:

```tsx
<div className="px-2 py-1 text-[11px] uppercase tracking-widest font-semibold text-[var(--color-sidebar-section)]">
  Group Label
</div>
```

---

## 4. Spacing & Layout

### 4.1 App shell

```
┌──────────┬──────────────────────────────┐
│          │  Header (h-12)               │
│ Sidebar  ├──────────────────────────────┤
│ (w-60)   │  Main content (p-6)          │
│          │                              │
│          │                              │
└──────────┴──────────────────────────────┘
```

- Sidebar: `w-60` expanded, `w-12` collapsed, collapsible via `Ctrl/Cmd+B`
- Header: `h-12`, contains page title + search trigger + theme toggle
- Main content: `p-6`, scrollable with hidden scrollbars (opt-in `.scrollbar` class)

### 4.2 Page structure

Every page follows this pattern:

```tsx
<div className="h-full flex flex-col">
  <PageHeader title="Page Name" actions={<Button>Action</Button>} />
  {/* Filters/tabs */}
  <div className="flex gap-1 mb-4">...</div>
  {/* Content */}
  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
    ...
  </div>
</div>
```

### 4.3 Common spacing values

| Value | Usage |
|-------|-------|
| `gap-1` | Between filter tab buttons |
| `gap-1.5` | Between badge icon and text, between action buttons |
| `gap-2` | Between status buttons, between input elements |
| `gap-3` | Grid cards gap, between filter groups |
| `gap-4` | Between major sections in modals/panels |
| `mb-1` | After section header to content |
| `mb-2` | After filter tabs, after section labels |
| `mb-3` | After context banners |
| `mb-4` | After filter bars to content |
| `mb-6` | PageHeader to content (via PageHeader component) |
| `p-3` | Code blocks, raw text blocks |
| `p-4` | Card padding |
| `px-6 py-4` | Modal content padding |
| `px-3 py-2` | Chat message card padding, input inner padding |
| `py-1.5 px-2` | Clickable list row padding |

### 4.4 Scrollbar strategy

Scrollbars are **hidden by default** globally:

```css
::-webkit-scrollbar { display: none; }
* { scrollbar-width: none; }
```

Opt-in where needed with the `.scrollbar` class:

```css
.scrollbar::-webkit-scrollbar { display: block; width: 6px; height: 6px; }
.scrollbar::-webkit-scrollbar-track { background: transparent; }
.scrollbar::-webkit-scrollbar-thumb {
  background: var(--color-border-default);
  border-radius: 3px;
}
```

Apply to: main content area, thread lists, long modals.

---

## 5. Component Reference

### 5.1 Button

Four variants, three sizes:

| Variant | Style | Usage |
|---------|-------|-------|
| `primary` | Solid accent blue, white text | Primary actions (Create, Save) |
| `secondary` | White/surface bg, border, dark text | Secondary actions (Cancel, filter buttons) |
| `ghost` | Transparent, secondary text | Tertiary actions (collapse, menu triggers) |
| `danger` | Solid red, white text | Destructive actions |

| Size | Height | Text | Usage |
|------|--------|------|-------|
| `sm` | `h-7` (28px) | 11px | Inline actions, status buttons, filter tabs |
| `md` | `h-8` (32px) | 13px | Default button size |
| `lg` | `h-9` (36px) | 13px | Chat send, prominent actions |

Built-in `loading` prop shows spinner and disables interaction.

```tsx
<Button variant="secondary" size="sm" loading={isPending}>
  <Icon className="h-3.5 w-3.5 mr-1" /> Label
</Button>
```

### 5.2 Badge

Pill-shaped status indicators: `px-1.5 py-0.5 text-[11px] rounded-full`

| Variant | Style | Usage |
|---------|-------|-------|
| `default` | Grey background | Neutral labels |
| `success` | Green bg + border | Active, done, processed |
| `warning` | Amber bg + border | In progress, paused |
| `danger` | Red bg + border | Failed, dropped, overdue |
| `info` | Blue bg + border | Types, categories |
| `outline` | Transparent + border | Tags, link types, metadata |

### 5.3 Card

```tsx
<Card interactive onClick={handleClick} className="p-4 cursor-pointer">
  {/* content */}
</Card>
```

- Base: `bg-surface-primary`, `border-[0.5px] border-subtle`, `rounded-lg`
- Interactive: adds `hover:shadow-md hover:border-default transition-all duration-150`
- Half-pixel border (`border-[0.5px]`) is key — gives a subtle, refined look

### 5.4 Modal

Portal-based, three sizes:

| Size | Max width | Usage |
|------|-----------|-------|
| `sm` | 400px | Confirmation dialogs |
| `md` | 560px | Create forms, simple detail views |
| `lg` | 720px | Detail panels, entry views with lots of content |

Features:
- `backdrop-blur-[2px]` overlay (subtle, not heavy)
- Closes on Escape key and overlay click
- Optional `footer` slot for action buttons
- Title bar with close X button

### 5.5 Input / Select / Textarea

Consistent style across all form elements:

```
h-8, px-3, text-[13px], rounded-md
bg-[var(--color-input-bg)]
border border-[var(--color-input-border)]
focus:ring-2 focus:ring-[var(--color-input-focus-ring)] focus:border-transparent
```

- Optional `label` prop (rendered as `text-[13px] font-medium`)
- Optional `error` prop (rendered as `text-[11px] text-danger`)
- Textarea has `min-h-[100px]` and `resize-y`

### 5.6 Table

Compound component pattern:

```tsx
<Table>
  <Table.Head>
    <Table.Row>
      <Table.HeadCell>Name</Table.HeadCell>
    </Table.Row>
  </Table.Head>
  <Table.Body>
    <Table.Row>
      <Table.Cell>Value</Table.Cell>
    </Table.Row>
  </Table.Body>
</Table>
```

- Head cells: `text-[11px] uppercase tracking-wider font-medium text-tertiary`
- Body rows: `hover:bg-layer-hover transition-colors` with `group` class
- Cells: `py-2 px-2.5 text-[13px]`

### 5.7 Dropdown

Click-to-open, closes on outside click or Escape:

```tsx
<Dropdown
  trigger={<Button variant="ghost" size="sm"><MoreHorizontal /></Button>}
  items={[
    { label: "Edit", icon: Pencil, onClick: handleEdit },
    { label: "Delete", icon: Trash2, onClick: handleDelete, danger: true },
  ]}
  align="right"
/>
```

### 5.8 EmptyState

Centered with icon, title, description, and optional action:

```tsx
<EmptyState
  icon={Inbox}
  title="No items yet"
  description="Create your first item."
  action={<Button size="sm">Create</Button>}
/>
```

- Icon: `h-10 w-10 text-placeholder mb-3`
- Title: `text-[15px] font-medium`
- Description: `text-[13px] text-secondary max-w-xs`

### 5.9 Spinner

CSS-only spinning border:

```tsx
<Spinner size="sm" />  /* h-4 w-4 */
<Spinner size="md" />  /* h-6 w-6 (default) */
<Spinner size="lg" />  /* h-8 w-8 */
```

Uses `animate-spin`, `border-accent`, `border-t-transparent`.

### 5.10 CommandPalette

`Cmd+K` triggered, portal-based:

- Positioned at `pt-[20vh]` from top
- Search input + results list
- Keyboard navigation (arrows + enter)
- Two result types: page navigation + entry search
- Same overlay pattern as Modal (`bg-black/40 backdrop-blur-[2px]`)

---

## 6. Layout Components

### 6.1 Sidebar

- Dark background in both themes (always `#111827` / `#09090b`)
- Collapsible: `w-60` ↔ `w-12`, toggled via button or `Ctrl+B`
- Persists collapsed state in `localStorage`
- Navigation grouped by sections with uppercase labels
- Active link: `bg-sidebar-bg-active text-sidebar-text-active font-medium`
- Inactive link: `text-sidebar-text hover:bg-sidebar-bg-hover`
- Brand at top: "LifeOS" in `text-[15px] font-bold`, subtitle in `text-[11px]`

### 6.2 Header

- Height: `h-12`
- Contains: page title (derived from route), search trigger, theme toggle
- Search trigger shows `Cmd+K` keyboard shortcut badge
- Theme cycles: light → dark → system
- Background: `surface-primary` with `border-b border-subtle`

### 6.3 PageHeader

Used at the top of every page:

```tsx
<PageHeader
  title="Page Title"
  description="Optional subtitle"
  actions={<Button>Action</Button>}
/>
```

- Title: `text-lg font-semibold`
- Bottom margin: `mb-6`

---

## 7. Interaction Patterns

### 7.1 Tab/filter bar

Inline button group, not actual tabs:

```tsx
<div className="flex gap-1 mb-4 overflow-x-auto">
  {tabs.map((tab) => (
    <button
      key={tab.value}
      onClick={() => setFilter(tab.value)}
      className={`px-3 py-1.5 text-[12px] rounded-md transition-colors ${
        active === tab.value
          ? "bg-[var(--color-layer-active)] text-[var(--color-text-primary)] font-medium"
          : "text-[var(--color-text-secondary)] hover:bg-[var(--color-layer-hover)]"
      }`}
    >
      {tab.label}
    </button>
  ))}
</div>
```

### 7.2 Card grid

```tsx
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
  {items.map((item) => (
    <Card interactive onClick={() => select(item.id)} className="p-4">
      {/* Title row with badge */}
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-[13px] font-semibold text-primary truncate flex-1 mr-2">
          {item.title}
        </h3>
        <Badge variant="info">{item.status}</Badge>
      </div>
      {/* Description */}
      <p className="text-[12px] text-secondary line-clamp-2 mb-2">{item.description}</p>
      {/* Metadata row */}
      <div className="flex items-center gap-3 text-[11px] text-tertiary">
        <span>{item.count} items</span>
        <span>{timeAgo(item.updated_at)}</span>
      </div>
    </Card>
  ))}
</div>
```

### 7.3 Clickable list rows

For items inside panels/modals:

```tsx
<div
  className="flex items-center justify-between text-[12px] py-1.5 px-2 rounded-md cursor-pointer hover:bg-[var(--color-layer-hover)] transition-colors"
  onClick={() => handleClick(item.id)}
>
  <span className="text-primary">{item.label}</span>
  <div className="flex items-center gap-2 shrink-0">
    <Badge variant="outline">{item.type}</Badge>
    <span className="text-tertiary">{timeAgo(item.date)}</span>
  </div>
</div>
```

### 7.4 Detail modal pattern

1. Grid page → click card → open modal with detail data
2. Modal fetches full data via separate hook
3. Shows Spinner while loading, "not found" if missing
4. Content sections with section headers

```tsx
function DetailModal({ id, onClose }) {
  const { data, isLoading } = useDetail(id);
  if (isLoading) return <Modal open onClose={onClose} title="Loading..."><Spinner /></Modal>;
  if (!data) return <Modal open onClose={onClose} title="Not found"><p>Not found.</p></Modal>;
  return (
    <Modal open onClose={onClose} title={data.title} size="lg">
      <div className="space-y-4">
        {/* badges row */}
        {/* content sections */}
        {/* actions */}
      </div>
    </Modal>
  );
}
```

### 7.5 Chat message pattern

```
┌──────────────────────────────────────┐
│  [user message, right-aligned]       │
│                    ┌────────────────┐ │
│                    │ Message text   │ │
│                    └────────────────┘ │
│  ┌────────────────┐                   │
│  │ Assistant reply │                  │
│  │ [action buttons]│                  │
│  └────────────────┘                   │
│  ┌────────────────┐                   │
│  │ ⟳ Thinking...  │  (while loading) │
│  └────────────────┘                   │
└──────────────────────────────────────┘
```

- User messages: `ml-auto max-w-[80%]` with `bg-accent-muted`
- Assistant messages: `mr-auto max-w-[80%]`
- Thinking state: spinner icon + "Thinking..." text
- Error state: red border card with error message
- Input disabled while waiting for reply

### 7.6 Loading states

| State | Pattern |
|-------|---------|
| Page loading | `<Spinner />` centered |
| Button loading | `loading` prop → inline spinner + disabled |
| Async reply | Thinking bubble with `Loader2 animate-spin` |
| Empty data | `<EmptyState icon={...} title="..." />` |

---

## 8. Dark Mode Implementation

### 8.1 How it works

1. `useTheme()` hook manages `light | dark | system` preference in localStorage
2. Applies/removes `.dark` class on `<html>` element
3. All colors reference CSS custom properties that change under `.dark`
4. System preference detected via `prefers-color-scheme` media query

### 8.2 Dark mode color strategy

- **Light mode**: Use solid hex colors for backgrounds, solid for status muted
- **Dark mode**: Use `rgba()` with low opacity for muted/subtle colors

```css
/* Light: solid pastel */
--color-success-muted: #ecfdf5;
--color-success-muted-border: #a7f3d0;

/* Dark: semi-transparent tints */
--color-success-muted: rgba(16, 185, 129, 0.12);
--color-success-muted-border: rgba(16, 185, 129, 0.25);
```

This makes status badges and colored backgrounds work naturally on dark surfaces.

### 8.3 Theme toggle UX

Cycles through: Light (Sun icon) → Dark (Moon icon) → System (Monitor icon)

---

## 9. Animation & Transitions

### 9.1 Transitions

Always use `transition-colors duration-150` for hover states. For cards, use `transition-all duration-150` to animate shadow + border together.

### 9.2 Sidebar collapse

`transition-[width] duration-200` — only animates width, not content.

### 9.3 Reduced motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

### 9.4 Keyframe animations

- Modal entrance: `animate-[modal-in_200ms_ease-out]`
- Dropdown entrance: `animate-[dropdown-in_100ms_ease-out]`
- Spinner: `animate-spin` (Tailwind built-in)
- Loading icon: `animate-spin` on Lucide `Loader2`

---

## 10. Icon Conventions

Using **Lucide React** exclusively. Icon sizing is consistent:

| Context | Size | Example |
|---------|------|---------|
| Navigation items | `h-4 w-4` | Sidebar nav, dropdown items |
| Button inline icon | `h-3.5 w-3.5` | Button with icon + text, use `mr-1` gap |
| Small inline icon | `h-3 w-3` | Convert arrows, note indicators |
| Empty state icon | `h-10 w-10` | Large centered icon |
| Header/toolbar | `h-4 w-4` | Search, theme toggle |

Always use `shrink-0` on icons inside flex containers to prevent compression.

---

## 11. Data Fetching Patterns

### 11.1 API client

Minimal fetch wrapper — no axios:

```typescript
const BASE = "/api";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? "Request failed");
  }
  return res.json() as Promise<T>;
}
```

### 11.2 Query hooks

One hook file per resource. Pattern:

```typescript
// List query
export function useItems(filter?: string) {
  return useQuery<{ items: Item[]; total: number }>({
    queryKey: ["items", filter],
    queryFn: () => apiFetch(`/items${filter ? `?status=${filter}` : ""}`),
  });
}

// Detail query
export function useItem(id: string | null) {
  return useQuery<ItemDetail>({
    queryKey: ["items", id],
    queryFn: () => apiFetch(`/items/${id}`),
    enabled: !!id,
  });
}

// Mutation
export function useCreateItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateInput) =>
      apiFetch<Item>("/items", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["items"] });
    },
  });
}
```

### 11.3 Query key conventions

- List: `["resource-name", filterValue]`
- Detail: `["resource-name", id]`
- Always invalidate the list key after mutations

---

## 12. File Structure

```
src/
  api/
    client.ts              → fetch wrapper + ApiError class
    types.ts               → ALL TypeScript interfaces (one file)
    hooks/
      useEntries.ts        → useInbox, useTimeline, useCapture, useEntry, etc.
      useTasks.ts          → useTasks, useUpdateTask, etc.
      useGoals.ts          → useGoals, useGoalDashboard, etc.
      useIdeas.ts          → useIdeas, useIdea, useCreateIdea, etc.
      ...one file per resource
  components/
    ui/
      Button.tsx           → 4 variants, 3 sizes, loading state
      Badge.tsx            → 6 variants (default/success/warning/danger/info/outline)
      Card.tsx             → Base + interactive mode
      Modal.tsx            → Portal-based, 3 sizes, Escape to close
      Input.tsx            → Label + error support
      Select.tsx           → Native select with custom chevron
      Textarea.tsx         → Auto-resize support
      Table.tsx            → Compound component (Table.Head, Table.Row, etc.)
      Dropdown.tsx         → Click menu with outside-click dismiss
      Spinner.tsx          → CSS-only loading indicator
      EmptyState.tsx       → Icon + title + description + action
    layout/
      AppShell.tsx         → Sidebar + Header + main content area
      Sidebar.tsx          → Collapsible nav with groups
      Header.tsx           → Page title + search + theme toggle
      PageHeader.tsx       → Title + description + actions slot
    CommandPalette.tsx     → Cmd+K search overlay
  pages/
    dashboard/DashboardPage.tsx
    tasks/TasksPage.tsx
    goals/GoalsPage.tsx
    ideas/
      IdeasPage.tsx
      EntryDetailModal.tsx
    ...one folder per route
  hooks/
    useTheme.ts            → Light/dark/system toggle with localStorage
    useDebounce.ts         → Debounce hook for search
  lib/
    cn.ts                  → clsx wrapper (single line)
    formatters.ts          → timeAgo, truncate, formatDate
    constants.ts           → NAV_GROUPS, ENTRY_TYPES
  index.css                → All design tokens, base styles, scrollbar
  App.tsx                  → React Router routes
  main.tsx                 → Entry point
```

---

## 13. Key Design Principles

1. **13px base font** — Dense but readable. Everything is one notch smaller than typical web apps.

2. **Information density over whitespace** — Plane/Linear-inspired. Cards show 3 rows of info. Tables are compact. Spacing is tight.

3. **CSS variables for everything** — No hardcoded colors in components. Theme swaps by changing variables.

4. **Half-pixel borders on cards** — `border-[0.5px]` gives a subtle, refined look that full 1px borders don't.

5. **Dark sidebar, always** — The sidebar is dark in both light and dark modes. It anchors the layout.

6. **No component library dependency** — Every component is < 100 lines, fully understood, fully customizable.

7. **Status colors use three tiers** — Solid (text/icon), muted (background), muted-border. This creates consistent badges and status indicators.

8. **Shadows use blue-grey, not black** — `rgba(41, 47, 61, ...)` feels softer and more refined than pure black shadows.

9. **Portals for overlays** — Modals and command palette render via `createPortal(...)` to `document.body`, avoiding z-index stacking issues.

10. **One type file, one hook file per resource** — All interfaces in `types.ts`, all hooks for a resource in one `use{Resource}.ts` file. Simple to navigate.

---

## 14. Quick Start Template

To reproduce this design system in a new project:

```bash
npm create vite@latest my-app -- --template react-ts
cd my-app
npm install @tanstack/react-query react-router-dom lucide-react clsx @fontsource-variable/inter
npm install -D tailwindcss @tailwindcss/vite
```

Then:
1. Copy `index.css` with all CSS custom properties
2. Copy the `components/ui/` folder as-is
3. Copy `components/layout/` (AppShell, Sidebar, Header, PageHeader)
4. Copy `lib/cn.ts` and `lib/formatters.ts`
5. Copy `hooks/useTheme.ts`
6. Set up `api/client.ts` with your API base URL
7. Create your `types.ts` and hook files following the patterns above

The entire UI component layer is ~800 lines of code total. No dependencies beyond Tailwind, clsx, and Lucide.
