"""Local-only Discord configuration window. Never connects to Discord or AWS."""

from __future__ import annotations

import csv
import io
import os
import re
import subprocess
import tempfile
from pathlib import Path

from dotenv import dotenv_values

FIELDS = (
    ("BOT_OWNER_ID", "Your Discord user ID"),
    ("DISCORD_APPLICATION_ID", "Application ID"),
    ("DISCORD_PUBLIC_KEY", "Public key"),
    ("DISCORD_TOKEN", "Bot token"),
    ("CLAN_GUILD_ID", "Clan server ID (optional for now)"),
)


def validate(values):
    cleaned = {key: values.get(key, "").strip() for key, _ in FIELDS}
    for key, label in FIELDS:
        value = cleaned[key]
        if key == "CLAN_GUILD_ID" and not value:
            continue
        if not value:
            raise ValueError(f"Enter {label.lower()}.")
        if key.endswith("_ID") and not re.fullmatch(r"[0-9]{17,20}", value):
            raise ValueError(f"{label} must contain 17–20 digits.")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", cleaned["DISCORD_PUBLIC_KEY"]):
        raise ValueError("The public key must contain 64 hexadecimal characters.")
    if not re.fullmatch(r"[A-Za-z0-9._-]{20,}", cleaned["DISCORD_TOKEN"]):
        raise ValueError("Check the token: use the token only, without spaces or a Bot prefix.")
    return cleaned


def restrict_file(path):
    if os.name == "nt":
        result = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        sid = next(csv.reader(io.StringIO(result.stdout)))[1]
        subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"*{sid}:(F)"],
            capture_output=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        path.chmod(0o600)


def save_config(path, values):
    path = Path(path)
    cleaned = validate(values)
    previous = dict(dotenv_values(path)) if path.exists() else {}
    for key, value in cleaned.items():
        if value or key not in previous:
            previous[key] = value
    previous.setdefault("AWS_REGION", "us-east-2")
    if previous["AWS_REGION"] != "us-east-2":
        raise ValueError(
            "Existing AWS_REGION differs from the approved us-east-2. Check the configuration."
        )
    descriptor, name = tempfile.mkstemp(prefix=".discord-config-", suffix=".env", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        # Restrict the empty file BEFORE any credential is written, and carry its ACL to .env.
        restrict_file(temporary)
        lines = ["# Private local Discord configuration. Never commit or share this file.\n"]
        for key, value in previous.items():
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                raise ValueError(
                    "The existing configuration contains an unsupported variable name."
                )
            if value is None:
                lines.append(f"{key}\n")
            else:
                escaped = value.replace("\\", "\\\\").replace("'", "\\'")
                lines.append(f"{key}='{escaped}'\n")
        temporary.write_text("".join(lines), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    import tkinter as tk
    from tkinter import ttk

    path = Path(__file__).with_name(".env")
    existing = dotenv_values(path) if path.exists() else {}
    root = tk.Tk()
    root.title("Discord clan bot — private setup")
    root.geometry("650x540")
    root.minsize(590, 520)
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Discord bot setup", font=("Segoe UI", 18, "bold")).pack(anchor="w")
    ttk.Label(frame, text="Saved only on this PC. The bot will remain stopped.").pack(
        anchor="w", pady=(4, 18)
    )
    entries = {}
    for key, label in FIELDS:
        ttk.Label(frame, text=label).pack(anchor="w", pady=(5, 2))
        entry = ttk.Entry(frame, show="•" if key == "DISCORD_TOKEN" else "", font=("Segoe UI", 11))
        entry.insert(0, existing.get(key) or "")
        entry.pack(fill="x", ipady=3)
        entries[key] = entry
    status = tk.StringVar()
    ttk.Label(frame, textvariable=status, wraplength=575).pack(anchor="w", pady=(16, 8))

    def save():
        try:
            save_config(path, {key: entry.get() for key, entry in entries.items()})
        except ValueError as exc:
            status.set(str(exc))
        except Exception:
            # Never surface a traceback, credential value, or failed subprocess output.
            status.set(
                "Could not securely save the file. Your existing configuration was left intact."
            )
        else:
            status.set("Saved privately to .env. The bot has not been started.")
            entries["DISCORD_TOKEN"].delete(0, "end")
            button.configure(state="disabled")

    button = ttk.Button(frame, text="Save privately", command=save)
    button.pack(anchor="e")
    entries["BOT_OWNER_ID"].focus_set()
    root.mainloop()


if __name__ == "__main__":
    main()
