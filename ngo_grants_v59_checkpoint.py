"""Durable Git checkpoint before each Telegram send for v5.9.

IMPORTANT: save_state() alone only updates the runner filesystem; the legacy
workflow pushes after the Python process ends. That is NOT a crash-safe
acknowledgement boundary. This module pushes the updated outbox to main
synchronously, failing closed if a remote checkpoint cannot be confirmed.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Callable, Sequence


def durable_checkpoint(state: dict, *, save_local: Callable[[dict], None],
                       state_path: Path, repo_root: Path | None = None,
                       runner: Callable[..., object] = subprocess.run,
                       artifact_paths: Sequence[Path] = ()) -> None:
    """Persist to origin/main before returning; never send after failed push."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Доставка v5.9 дозволена лише в GitHub Actions")
    if os.environ.get("NGO_GRANTS_V59_LIVE_DELIVERY") != "true":
        raise RuntimeError("Доставка v5.9 явно не активована")
    root = Path(repo_root or Path.cwd()).resolve()
    relative = state_path.resolve().relative_to(root) if state_path.is_absolute() else state_path
    if relative.as_posix() != "ai_catalogs/state.json":
        raise RuntimeError("Невірний шлях стану для підтвердження доставки")

    def git(*arguments: str) -> str:
        result = runner(["git", *arguments], cwd=str(root), text=True,
                        capture_output=True, check=True)
        return str(getattr(result, "stdout", "")).strip()

    try:
        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        if branch != "main":
            raise RuntimeError("Не можна підтверджувати доставку поза main")
        save_local(state)
        git("config", "user.name", "github-actions[bot]")
        git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
        staged = [relative.as_posix()]
        for artifact in artifact_paths:
            candidate = Path(artifact)
            if candidate.is_absolute():
                artifact_rel = candidate.resolve().relative_to(root)
            else:
                artifact_rel = candidate
            normalized = artifact_rel.as_posix()
            if (not normalized.startswith("ai_catalogs/pdfs/")
                    or not normalized.endswith(".pdf")
                    or ".." in artifact_rel.parts
                    or not (root / artifact_rel).is_file()):
                raise RuntimeError("Неприпустимий або відсутній PDF для durable checkpoint")
            staged.append(normalized)
        git("add", "--", *staged)
        changes = git("diff", "--cached", "--name-only")
        staged_set = set(staged)
        if any(p not in staged_set for p in changes.splitlines()):
            raise RuntimeError("В індексі несподівані файли; доставку заблоковано")
        if changes:
            git("commit", "-m", "Checkpoint NGO Grants v5.9 Telegram outbox")
        git("pull", "--rebase", "origin", "main")
        git("push", "origin", "HEAD:main")
        current = git("rev-parse", "HEAD")
        remote = git("ls-remote", "origin", "refs/heads/main")
        remote_sha = remote.split()[0] if remote else ""
        if not remote_sha or remote_sha != current:
            raise RuntimeError("Не підтверджено стан черги на GitHub main")
    except (subprocess.CalledProcessError, OSError, ValueError) as exc:
        raise RuntimeError(
            "Немає підтвердженого durable Git checkpoint. "
            "Telegram відправлення заблоковано."
        ) from exc
