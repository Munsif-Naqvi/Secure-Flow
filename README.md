# SecureFlow

A VS Code extension plus a Python engine that finds security problems (Broken Access Control and Unsafe Input Handling) in Python Flask apps.

- `docs/`: project documents (start with `docs/01-project-brief.md`)
- `engine/`: Python engine (static analysis), run with `python engine/main.py <project_folder>`
- `extension/`: VS Code extension (TypeScript, esbuild). Open this folder in VS Code and press F5 to run it.
- `corpus/`: test Flask apps with ground truth

See `CLAUDE.md` for the current phase and how to work in this repo.
