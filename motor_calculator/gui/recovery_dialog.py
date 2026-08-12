"""Small recovery browser for local autosave snapshots."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from motor_calculator.i18n import localize_message, localize_status, tr
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
        self.window.title(tr("recovery.title"))
        self.window.transient(parent)
        self.window.geometry("900x360")
        self.window.minsize(700, 300)
        self._build()

    def _build(self) -> None:
        intro = ttk.Label(
            self.window,
            text=tr("recovery.intro"),
            wraplength=840,
        )
        intro.pack(fill=tk.X, padx=14, pady=(14, 8))
        columns = ("project", "time", "path", "status", "newer")
        self.tree = ttk.Treeview(self.window, columns=columns, show="headings", height=9)
        headings = {
            "project": tr("recovery.project"),
            "time": tr("recovery.time"),
            "path": tr("recovery.path"),
            "status": tr("recovery.status"),
            "newer": tr("recovery.newer"),
        }
        widths = {"project": 150, "time": 165, "path": 300, "status": 120, "newer": 110}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], stretch=column == "path")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=14)
        self._populate()
        buttons = ttk.Frame(self.window)
        buttons.pack(fill=tk.X, padx=14, pady=12)
        ttk.Button(buttons, text=tr("recovery.restore"), command=self._restore).pack(side=tk.LEFT)
        ttk.Button(buttons, text=tr("recovery.discard"), command=self._discard).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text=tr("common.details"), command=self._details).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text=tr("recovery.later"), command=self.window.destroy).pack(side=tk.RIGHT)

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
                    record.original_project_path or tr("common.never_saved"),
                    localize_status(candidate.status),
                    tr("common.yes") if candidate.newer_than_official else tr("common.no")
                    if candidate.newer_than_official is False else tr("common.not_applicable"),
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
            tr("recovery.discard_title"),
            tr("recovery.discard_question"),
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
        details = tr(
            "recovery.details",
            project=record.project.metadata.project_name,
            path=record.original_project_path or tr("common.never_saved"),
            time=record.recovery_timestamp,
            last_save=record.last_normal_save_timestamp or tr("common.unknown"),
            app_version=record.application_version,
            schema=record.project_schema_version,
            dirty=tr("common.yes") if record.dirty else tr("common.no"),
            newer=tr("common.yes") if candidate.newer_than_official else tr("common.no")
            if candidate.newer_than_official is False else tr("common.not_applicable"),
            sources=", ".join(localize_status(priority) for priority in candidate.priorities),
            details=localize_message(candidate.details),
        )
        messagebox.showinfo(tr("recovery.details_title"), details, parent=self.window)
