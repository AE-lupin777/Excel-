# ULAgent Resource Timeline Viewer

Resource Timeline Viewer development workspace.

## Directory layout

- `src/viewer/` Viewer source
- `config/` Viewer configuration
- `docs/` specifications, design notes, and manuals
- `tests/` test code and test definitions
- `samples/evidence/` local sample Evidence only
- `tools/` development/helper scripts

## Important design rules

- A (file placement completion time) is an independent event. Do not substitute another point for A.
- Preserve raw timestamps. Do not silently correct clock differences between PCs.
- Treat zero and missing data as different values.
- Status API data is not SQLite internal SQL execution tracing.
- AI analysis is prompt generation only. The Viewer does not connect to an AI API.
- Users review and copy generated prompts themselves.
