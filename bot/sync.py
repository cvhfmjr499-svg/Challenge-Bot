"""Keep a PC clone in step with GitHub while the live runner and the cloud routines both trade.

The live runner never keeps commits of its own: before each step it moves to origin/main,
and after the step it pushes the new state. If the push is rejected (a cloud routine pushed
first), the next step simply starts again from origin. That is safe because an update is
deterministic: processing the same bars from the same state gives the same result.
"""
import subprocess

from .config import ROOT


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=120)


def available():
    return (ROOT / ".git").exists() and _git("--version").returncode == 0


def pull():
    """Move to origin/main. Returns an error text or None."""
    r = _git("fetch", "-q", "origin", "main")
    if r.returncode:
        return r.stderr.strip() or "git fetch fehlgeschlagen"
    r = _git("reset", "-q", "--hard", "origin/main")
    return (r.stderr.strip() or "git reset fehlgeschlagen") if r.returncode else None


def push(message):
    """Commit data/ and push. Returns an error text or None."""
    _git("add", "data")
    if _git("diff", "--cached", "--quiet").returncode == 0:
        return None
    r = _git("-c", "user.name=Challenge Bot (Live)", "-c", "user.email=bot@local",
             "commit", "-q", "-m", message)
    if r.returncode:
        return r.stderr.strip() or "git commit fehlgeschlagen"
    r = _git("push", "-q", "origin", "main")
    return (r.stderr.strip() or "git push abgelehnt") if r.returncode else None
