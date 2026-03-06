# Kanban Studio Frontend AGENTS.md

## Overview
This directory contains the Next.js frontend for the Project Management MVP web app. It implements a single-board Kanban system with drag-and-drop, column renaming, card editing, and a modern UI.

## App Structure
- **App Entrypoint:**
  - `src/app/layout.tsx`: Sets up global fonts, theme, and layout.
  - `src/app/page.tsx`: Renders the KanbanBoard as the homepage.
  - `src/app/globals.css`: Defines color scheme and global styles (see project color variables).

- **Kanban Components:**
  - `KanbanBoard.tsx`: Main board logic, manages board state, drag-and-drop, and overlays.
  - `KanbanColumn.tsx`: Renders columns, supports renaming, card display, and new card creation.
  - `KanbanCard.tsx`: Individual card, supports deletion and drag sorting.
  - `KanbanCardPreview.tsx`: Card preview for drag overlay.
  - `NewCardForm.tsx`: Handles new card creation with title/details form.

- **Data Model:**
  - `lib/kanban.ts`: Types for Card, Column, BoardData. Provides initial board data and card movement logic (`moveCard`, `createId`).

## Features
- Five fixed columns (Backlog, Discovery, In Progress, Review, Done)
- Cards can be moved between columns or reordered
- Columns can be renamed inline
- Cards can be added, edited, or deleted
- Drag-and-drop powered by `@dnd-kit`
- Responsive, accessible UI with custom color scheme

## Testing
- `KanbanBoard.test.tsx`: UI tests for board, column, and card interactions
- `kanban.test.ts`: Unit tests for board data logic (card movement)
- Run tests: `npm run test:unit` (unit), `npm run test:e2e` (end-to-end)

## Styling
- Uses Tailwind CSS for utility-first styling
- Custom color variables in `globals.css` (see AGENTS.md for color scheme)

## Project Scripts
- `npm run dev`: Start local dev server
- `npm run build`: Build for production
- `npm run test:unit`: Run unit tests
- `npm run test:e2e`: Run end-to-end tests

## Limitations
- No backend/API integration (demo only)
- No authentication
- No AI sidebar/chat

## Next Steps
- Integrate backend API for persistence
- Add authentication flow
- Implement AI chat sidebar for card creation/editing

---
This file is for agent documentation and onboarding. Update as features evolve.