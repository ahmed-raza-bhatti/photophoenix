"""'Learn cameras from…' window: add healthy-photo folders (or whole drives) to the camera library."""
import json, os, string, threading, time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from . import engine

EXPLAINER = (
    "PhotoPhoenix rebuilds each encrypted photo using the JPEG settings (\"header\") of a healthy "
    "photo taken with the same phone or camera model. The more healthy photos it has seen, the "
    "more of your cameras it can match, and the better the colours.\n\n"
    "What it reads: only the first ~128 KB of each .jpg/.jpeg (the header), never the whole photo. "
    "It keeps the headers in a camera library on this PC (local/library.json); no picture data, "
    "nothing uploaded. Encrypted files, system folders, program folders and app caches are skipped.\n\n"
    "Good sources: old phones' photos copied to the PC, SD cards, backups, downloaded cloud "
    "photos. Photos re-saved by chat apps help less (their settings differ from the camera's).\n\n"
    "A whole PC can take a while. It runs at low priority and you can stop it at any time; "
    "whatever was learned so far is kept.")


def list_drives():
    if hasattr(os, "listdrives"):  # Python 3.12+ on Windows
        return [d for d in os.listdrives() if os.path.isdir(d)]
    if os.name == "nt":
        return [f"{c}:\\" for c in string.ascii_uppercase if os.path.isdir(f"{c}:\\")]
    return ["/"]


class LearnWindow:
    def __init__(self, parent, settings, title="PhotoPhoenix"):
        self.s, self.title = settings, title
        self.stop_flag, self.running = threading.Event(), False
        w = self.win = tk.Toplevel(parent)
        w.title(f"{title} — learn cameras from healthy photos")
        w.geometry("640x560"); w.minsize(520, 460); w.transient(parent)
        pad = dict(padx=10, pady=6)
        ttk.Label(w, text=EXPLAINER, wraplength=600, justify="left").pack(fill="x", **pad)

        mid = ttk.Frame(w); mid.pack(fill="both", expand=True, **pad)
        self.folders = tk.Listbox(mid, height=7, selectmode="extended")
        self.folders.pack(side="left", fill="both", expand=True)
        side = ttk.Frame(mid); side.pack(side="left", fill="y", padx=(8, 0))
        self.add_btn = ttk.Button(side, text="Add folder…", command=self.add_folder)
        self.pc_btn = ttk.Button(side, text="Add whole PC", command=self.add_whole_pc)
        self.rm_btn = ttk.Button(side, text="Remove", command=self.remove)
        for b in (self.add_btn, self.pc_btn, self.rm_btn): b.pack(fill="x", pady=2)

        self.bar = ttk.Progressbar(w, mode="indeterminate"); self.bar.pack(fill="x", **pad)
        self.status = tk.StringVar(value=self.library_summary())
        ttk.Label(w, textvariable=self.status, wraplength=600, justify="left").pack(fill="x", padx=10)
        bot = ttk.Frame(w); bot.pack(fill="x", **pad)
        self.go_btn = ttk.Button(bot, text="Start learning", command=self.start)
        self.stop_btn = ttk.Button(bot, text="Stop", command=self.stop, state="disabled")
        self.go_btn.pack(side="left"); self.stop_btn.pack(side="left", padx=6)
        ttk.Button(bot, text="Close", command=self.close).pack(side="right")
        w.protocol("WM_DELETE_WINDOW", self.close)

    def library_summary(self):
        try:
            with open(self.s.library_path, encoding="utf-8") as fh:
                n = len(json.load(fh))
            return f"Camera library: {n} camera/size types learned so far."
        except Exception:
            return "Camera library: empty — nothing learned yet."

    def add_folder(self):
        d = filedialog.askdirectory(parent=self.win, initialdir=os.path.expanduser("~"))
        if d and os.path.normpath(d) not in self.folders.get(0, "end"):
            self.folders.insert("end", os.path.normpath(d))

    def add_whole_pc(self):
        drives = list_drives()
        if not messagebox.askyesno(self.title, "Add every drive on this PC?\n\n" + "  ".join(drives) +
                                   "\n\nOnly photo headers are read, at low priority, skipping system and "
                                   "program folders. If a drive is old or failing, remove it from the list.",
                                   parent=self.win):
            return
        have = set(self.folders.get(0, "end"))
        for d in drives:
            if d not in have: self.folders.insert("end", d)

    def remove(self):
        for i in reversed(self.folders.curselection()): self.folders.delete(i)

    def start(self):
        roots = list(self.folders.get(0, "end"))
        if not roots:
            messagebox.showinfo(self.title, "Add at least one folder first.", parent=self.win); return
        self.running = True; self.stop_flag.clear()
        for b in (self.go_btn, self.add_btn, self.pc_btn, self.rm_btn): b.config(state="disabled")
        self.stop_btn.config(state="normal"); self.bar.start(12)
        threading.Thread(target=self.job, args=(roots,), daemon=True).start()

    def stop(self):
        self.stop_flag.set(); self.status.set("Stopping… keeping what was learned so far.")

    def job(self, roots):
        t0 = time.time(); seen = [0]
        def progress(n):
            seen[0] = n
            self.win.after(0, self.status.set, f"Read {n:,} photos' headers ({time.time() - t0:.0f}s)…")
        skip = [self.s.data_dir.lower()] + [d.lower() for d in self.s.skip_dirs]
        if self.s.output_dir: skip.append(os.path.abspath(self.s.output_dir).lower())
        new = engine.scan_library(roots, skip, progress=progress, should_stop=self.stop_flag.is_set)
        try:
            with open(self.s.library_path, encoding="utf-8") as fh: old = json.load(fh)
        except Exception:
            old = []
        merged, added = engine.merge_library(old, new)
        os.makedirs(self.s.data_dir, exist_ok=True)
        tmp = self.s.library_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh: json.dump(merged, fh)
        os.replace(tmp, self.s.library_path)
        stopped = self.stop_flag.is_set()
        msg = (f"{'Stopped' if stopped else 'Done'}: read {seen[0]:,} photos' headers in {time.time() - t0:.0f}s. "
               f"{added} new camera/size types learned; the library now has {len(merged)}.\n"
               + ("No new cameras: these photos come from cameras PhotoPhoenix already knew." if added == 0 else
                  "New cameras are used the next time you press Start (photos already recovered are not redone)."))
        self.win.after(0, self.finish, msg)

    def finish(self, msg):
        self.running = False; self.bar.stop()
        for b in (self.go_btn, self.add_btn, self.pc_btn, self.rm_btn): b.config(state="normal")
        self.stop_btn.config(state="disabled"); self.status.set(msg)

    def close(self):
        if self.running:
            if not messagebox.askyesno(self.title, "Learning is running. Stop it and close?\n"
                                       "What was learned so far is kept.", parent=self.win):
                return
            self.stop_flag.set()
            self.win.after(500, self.close_when_done); return
        self.win.destroy()

    def close_when_done(self):
        if self.running: self.win.after(500, self.close_when_done)
        else: self.win.destroy()
