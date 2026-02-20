# Next Action Items — LifeOS

## High Priority

### 1. Unlink / Re-link entries from ideas
- Allow removing an entry from an idea (DELETE idea_entries row)
- Allow manually linking an existing entry to a different idea
- Add UI controls (unlink button on entry row, "Link entry" action on idea detail)

### 2. Idea merge / split
- Merge two ideas into one (combine entries, pick surviving title)
- Split an idea into two (select which entries go where)
- Handles the case where LLM already over-grouped before the prompt fix

### 3. Bulk inbox processing feedback
- Show per-entry progress during process-inbox (currently all-or-nothing)
- WebSocket or SSE streaming for real-time processing status
- Display which entry is currently being processed and show success/fail per entry

### 4. Chat distill → insight cards pipeline
- After a goal/idea chat session, distill key takeaways into insight cards automatically
- Currently cards are created but the trigger is manual — add auto-distill on thread idle

## Medium Priority

### 5. Entry search inside idea detail
- When an idea has many linked entries, allow filtering/searching within them
- Fuzzy match on summary, raw_text, tags

### 6. Idea timeline / activity feed
- Show a chronological view of all events for an idea: created, entries linked, status changes, notes added
- Useful for understanding how an idea evolved over time

### 7. Dashboard widgets for ideas
- Ideas count by status (raw/exploring/mature)
- Recently active ideas
- Ideas with no entries in 7+ days (stale ideas)

### 8. Mobile-responsive refinements
- Chat page layout breaks on small screens (thread list + messages side by side)
- Ideas grid should collapse to single column on mobile
- Entry detail modal should be full-screen on mobile

## Low Priority / Polish

### 9. Keyboard shortcuts
- `n` to create new idea from Ideas page
- `Enter` to open selected idea
- `Esc` to close modals
- Arrow keys to navigate idea grid

### 10. Export / backup
- Export all ideas + entries as markdown or JSON
- One-click vault backup to zip

### 11. Tagging system for ideas
- Add tags to ideas (separate from entry tags)
- Filter ideas by tags on the Ideas page
- Auto-suggest tags from linked entries

### 12. Recurring review prompts
- Weekly prompt: "Review your exploring ideas — any ready to mature?"
- Surface parked ideas after N days: "Still interested in X?"
