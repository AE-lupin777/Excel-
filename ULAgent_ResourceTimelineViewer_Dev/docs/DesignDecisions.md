# Design decisions

1. Evidence and Viewer analysis are separate layers.
2. Explicit Error, Attention, Unknown, and Normal are distinct concepts.
3. FileId/FileName are used for evidence correlation where available.
4. A is Not Observed when no evidence exists. No inferred timestamp is inserted.
5. Resource gaps remain missing rather than being converted to zero.
6. AI output is a locally generated analysis prompt. No API call is implemented.
7. SQLite internal tracing is outside normal collection and may be considered only for secondary investigation.
