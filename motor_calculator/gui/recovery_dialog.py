"""Small recovery browser for local autosave snapshots."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from motor_calculator.project import RecoveryCandidate


class RecoveryBrowserDialog:
    def __init__(
        self,
        parent,
        candidates: tuple[RecoveryCandidate, ...],
        *,
        on_restore: Callable[[RecoveryCandidate], bool],
        on_discard: Callable[[RecoveryCandidate], bool],
    ) -> None:
        self.parent = parent
        self.candidates = list(candidates)
        self.on_restore = on_restore
        self.on_discard = on_discard
        self.window = tk.Toplevel(parent)
        self.window.title("Recover Unsaved Work")
        self.window.transient(parent)
        self.window.geometry("900x360")
        self.window.minsize(700, 300)
        self._build()

    def _build(self) -> None:
        intro = ttk.Label(
            self.window,
            text="Recovery snapshots are local safety copies. Restoring does not overwrite an official project file.",
            wraplength=840,
        )
        intro.pack(fill=tk.X, padx=14, pady=(14, 8))
        columns = ("project", "time", "path", "status", "newer")
        self.tree = ttk.Treeview(self.window, columns=columns, show="headings", height=9)
        headings = {
            "project": "Project/session",
            "time": "Recovery time",
            "path": "Original path",
            "status": "Status",
            "newer": "Newer than saved",
        }
        widths = {"project": 150, "time": 165, "path": 300, "status": 120, "newer": 110}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], stretch=column == "path")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=14)
        self._populate()
        buttons = ttk.Frame(self.window)
        buttons.pack(fill=tk.X, padx=14, pady=12)
        ttk.Button(buttons, text="Restore", command=self._restore).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Discard", command=self._discard).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text="Details", command=self._details).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text="Later", command=self.window.destroy).pack(side=tk.RIGHT)

    def _populate(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, candidate in enumerate(self.candidates):
            record = candidate.record
            self.tree.insert(
                "", tk.END, iid=str(index),
                values=(
                    record.project.metadata.project_name,
                    record.recovery_timestamp,
                    record.original_project_path or "(never saved)",
                    candidate.status.value,
                    "Yes" if candidate.newer_than_official else "No" if candidate.newer_than_official is False else "N/A",
                ),
            )
        if self.candidates:
            self.tree.selection_set("0")

    def _selected(self) -> RecoveryCandidate | None:
        selected = self.tree.selection()
        return None if not selected else self.candidates[int(selected[0])]

    def _restore(self) -> None:
        candidate = self._selected()
        if candidate is not None and self.on_restore(candidate):
            self.window.destroy()

    def _discard(self) -> None:
        candidate = self._selected()
        if candidate is None:
            return
        if not messagebox.askyesno(
            "Discard recovery",
            "Delete only this recovery snapshot? The official project file will not be changed.",
            parent=self.window,
        ):
            return
        if self.on_discard(candidate):
            self.candidates.remove(candidate)
            self._populate()
            if not self.candidates:
                self.window.destroy()

    def _details(self) -> None:
        candidate = self._selected()
        if candidate is None:
            return
        record = candidate.record
        details = (
            f"Project: {record.project.metadata.project_name}\n"
            f"Original path: {record.original_project_path or '(never saved)'}\n"
            f"Recovery time: {record.recovery_timestamp}\n"
            f"Last normal save: {record.last_normal_save_timestamp or '(unknown)'}\n"
            f"Application version: {record.application_version}\n"
            f"Project schema: {record.project_schema_version}\n"
            f"Dirty state: {record.dirty}\n"
            f"Newer than official: {candidate.newer_than_official}\n"
            f"Sources: {', '.join(priority.value for priority in candidate.priorities)}\n\n"
            f"{candidate.details}"
        )
        messagebox.showinfo("Recovery Details", details, parent=self.window)
