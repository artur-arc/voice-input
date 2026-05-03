# Contributing

## Reporting bugs

Open a [GitHub Issue](https://github.com/artur-arc/voice-input/issues) and include:

- macOS version (e.g. Sonoma 14.5)
- Chip model (e.g. M2 Pro)
- Relevant lines from `voice_input.log` — run `tail -50 voice_input.log` and paste what looks relevant

The log is usually enough to diagnose the problem, so please include it.

## Suggesting features

Open a [GitHub Issue](https://github.com/artur-arc/voice-input/issues) and describe the problem
you want solved. "I want X" is less useful than "When I do Y, I can't Z."

## Submitting a pull request

1. Fork the repo and create a branch for your change.
2. Keep the change small and focused — one thing per PR.
3. Open a pull request with a short description of what changed and why.

Avoid mixing refactors with behavior changes in the same PR.

## Development setup

```bash
git clone https://github.com/artur-arc/voice-input
cd voice-input
./setup.sh
source .venv/bin/activate
python src/main.py
```

`setup.sh` handles everything: virtual environment, Python packages, Whisper model download,
and macOS permissions. After that, `src/main.py` is the entry point.

Logs go to `voice_input.log` in the project root. `tail -f voice_input.log` shows live output.

## Code style

This is a Python project. Follow the patterns already in the codebase — naming conventions,
error handling, logging style. Do not add new dependencies unless there is no reasonable
alternative; the dependency list is intentionally small.
