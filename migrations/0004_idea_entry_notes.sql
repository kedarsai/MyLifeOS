-- Add a free-text note to each idea↔entry link
ALTER TABLE idea_entries ADD COLUMN note TEXT NOT NULL DEFAULT '';
