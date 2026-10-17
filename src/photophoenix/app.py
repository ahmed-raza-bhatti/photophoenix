"""PhotoPhoenix desktop app — progress bar, Pause/Resume, Stop, gentle on the computer.

Progress is saved to progress.json in the output folder; Start again with the same
folders to resume. Workers run at background priority and wait when RAM is low.
All defaults come from config (config.toml / .env / PHOTOPHOENIX_* environment variables).
"""
import csv, dataclasses, json, os, queue, threading, time
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from . import __version__, config, copies, engine, safety, video, video_index

TITLE = "PhotoPhoenix"
PHOTO_EXT = (".jpg.coot", ".jpeg.coot")
GREY_EXPLAINER = """The grey area is the top part of a photo that was inside the encrypted 150 KB.
That part of the picture can't be recovered: it is scrambled with a key only the
attackers have.

Keep it: the photo keeps its original size and the grey band shows honestly what is
missing.

Crop it off: the grey rows are removed. The photo is shorter than the original; the
picture itself is not re-compressed, so its quality is unchanged. report.csv marks
these photos as "cropped".

Save both: the full photo plus a copy named "... (cropped).jpg".

Photos restored from an untouched copy, or rebuilt from their own header, have no grey
area and are never cropped. Changing this choice later redoes the affected photos."""
COPIES_EXPLAINER = """Look for exact, unencrypted copies of your encrypted photos?

A copy gives a photo back complete. Most people find few or none, so don't count on it.

It WILL find: the exact same file saved twice, e.g. a folder copied to another drive, a
backup, a USB stick or SD card, a file-transfer app's folder, photos received in a chat app
and saved again.

It will NOT find:
 - photos that were re-saved or shrunk (most photos you SENT via WhatsApp, Facebook,
   Instagram, e-mail): they look the same but are different files
 - anything outside the folders below (not your whole PC, phone or cloud)
 - copies on drives the ransomware also encrypted

It only reads files. Nothing is changed, moved, deleted or uploaded.

Folders that will be searched:
{folders}

(To add more, list them under copy_search_dirs in config.toml.) Start the search?"""
SAVE_EVERY = 25  # results between progress.json saves (keeps disk writes low)
ICONS = {"ok": "✔", "review": "?", "failed": "✘"}


class App:
    def __init__(self, root, settings):
        self.root, self.cfg = root, settings
        root.title(f"{TITLE} {__version__} — recover photos from STOP/Djvu ransomware")
        root.geometry("880x640"); root.minsize(680, 500)
        self.events = queue.Queue()
        self.paused, self.stopping = threading.Event(), threading.Event()
        self.running, self.preview_img = False, None

        pad = dict(padx=8, pady=4)
        top = ttk.Frame(root); top.pack(fill="x", **pad)
        self.src = tk.StringVar(value=settings.source_dir); self.out = tk.StringVar(value=settings.output_dir)
        for r, (label, var) in enumerate((("Encrypted files", self.src), ("Save recovered to", self.out))):
            ttk.Label(top, text=label).grid(row=r, column=0, sticky="w")
            ttk.Entry(top, textvariable=var).grid(row=r, column=1, sticky="ew", padx=6)
            ttk.Button(top, text="Browse…", command=lambda v=var: self.browse(v)).grid(row=r, column=2)
        top.columnconfigure(1, weight=1)

        bar = ttk.Frame(root); bar.pack(fill="x", **pad)
        self.start_btn = ttk.Button(bar, text="Start", command=self.start)
        self.pause_btn = ttk.Button(bar, text="Pause", command=self.toggle_pause, state="disabled")
        self.stop_btn = ttk.Button(bar, text="Stop", command=self.stop, state="disabled")
        for b in (self.start_btn, self.pause_btn, self.stop_btn): b.pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="Workers").pack(side="left", padx=(12, 4))
        self.workers = tk.IntVar(value=settings.workers)
        ttk.Spinbox(bar, from_=1, to=settings.max_workers, width=3, textvariable=self.workers,
                    state="readonly").pack(side="left")
        ttk.Button(bar, text="Open output folder", command=self.open_out).pack(side="right")
        ttk.Button(bar, text="Learn cameras from…", command=self.learn_cameras).pack(side="right", padx=(0, 6))
        self.copies_btn = ttk.Button(bar, text="Find untouched copies", command=self.find_copies)
        self.copies_btn.pack(side="right", padx=(0, 6))

        grey = ttk.Frame(root); grey.pack(fill="x", padx=8)
        ttk.Label(grey, text="Grey area (the encrypted top of each photo):").pack(side="left")
        self.grey = tk.StringVar(value=settings.grey_area)
        for value, text in (("keep", "Keep it (shows what's missing)"), ("crop", "Crop it off"),
                            ("both", "Save both")):
            ttk.Radiobutton(grey, text=text, value=value, variable=self.grey).pack(side="left", padx=(8, 0))
        ttk.Button(grey, text="?", width=2, command=self.explain_grey).pack(side="left", padx=(8, 0))
        self.videos = tk.BooleanVar(value=settings.include_videos)
        ttk.Checkbutton(grey, text="Include videos", variable=self.videos).pack(side="right")

        self.progress = ttk.Progressbar(root, mode="determinate"); self.progress.pack(fill="x", **pad)
        self.status = tk.StringVar(value="Ready. Press Start.")
        ttk.Label(root, textvariable=self.status).pack(anchor="w", **pad)
        self.detail = tk.StringVar(value="")
        ttk.Label(root, textvariable=self.detail, foreground="#555").pack(anchor="w", padx=8)

        body = ttk.Frame(root); body.pack(fill="both", expand=True, **pad)
        self.log = tk.Listbox(body, activestyle="none")
        sb = ttk.Scrollbar(body, command=self.log.yview); self.log.config(yscrollcommand=sb.set)
        self.log.pack(side="left", fill="both", expand=True); sb.pack(side="left", fill="y")
        self.preview = ttk.Label(body, text="Latest recovered photo\nappears here", anchor="center", width=34)
        self.preview.pack(side="left", fill="both", padx=(8, 0))
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(150, self.poll)

    # ---------- UI actions ----------
    def browse(self, var):
        d = filedialog.askdirectory(initialdir=var.get() or os.path.expanduser("~"))
        if d: var.set(os.path.normpath(d))

    def open_out(self):
        if os.path.isdir(self.out.get()):
            if hasattr(os, "startfile"): os.startfile(self.out.get())

    def settings_for_run(self, src):
        s = dataclasses.replace(self.cfg, source_dir=src)
        return s

    def explain_grey(self):
        messagebox.showinfo(TITLE, GREY_EXPLAINER)

    def learn_cameras(self):
        from .learn_window import LearnWindow
        s = dataclasses.replace(self.cfg, source_dir=self.src.get().strip() or self.cfg.source_dir,
                                output_dir=self.out.get().strip() or self.cfg.output_dir)
        LearnWindow(self.root, s, TITLE)

    def find_copies(self):
        src = os.path.abspath(self.src.get())
        if not os.path.isdir(src):
            messagebox.showerror(TITLE, "Choose the encrypted files folder first."); return
        s = self.settings_for_run(src)
        roots = s.copy_roots()
        if not messagebox.askyesno(TITLE, COPIES_EXPLAINER.format(folders="\n".join("   " + r for r in roots))):
            return
        self.copies_btn.config(state="disabled")
        def job():
            stats = {}
            try:
                copies.find(src, roots, s.copies_path, skip=[d.lower() for d in s.skip_dirs],
                            progress=lambda m: self.events.put(("detail", m)), stats=stats)
            finally:
                self.events.put(("copies_done", stats))
        threading.Thread(target=job, daemon=True).start()

    def show_copies_result(self, st):
        total, found, verified = st.get("total", 0), st.get("found", 0), st.get("verified", 0)
        if not total:
            messagebox.showinfo(TITLE, "No encrypted files were found in the chosen folder."); return
        if found == 0:
            msg = (f"No untouched copies found for any of the {total} encrypted files.\n\n"
                   "This is the most common result. It only means no exact copy is in the folders "
                   "searched. Press Start to repair the photos from the data that survived.\n\n"
                   "If you have backups, old phones, SD cards or downloaded cloud photos, copy them "
                   "into a folder, add it to copy_search_dirs in config.toml, and search again.")
        else:
            unsure = found - verified
            msg = (f"Untouched copies found for {found} of {total} encrypted files "
                   f"({found / total:.1%}).\n\n"
                   f"   {verified} verified byte-for-byte (certain)\n"
                   + (f"   {unsure} matched by name and size only (small files; very likely, not certain)\n" if unsure else "")
                   + f"\nWhen you press Start, these {found} will be restored complete from their copies. "
                   f"The other {total - found} will be repaired from the surviving data as usual.")
        if st.get("in_list", found) > found:
            msg += f"\n\nCopies found by earlier searches are kept: the list now holds {st['in_list']} in total."
        messagebox.showinfo(TITLE, msg)

    def start(self):
        if not self.src.get().strip() or not self.out.get().strip():
            messagebox.showerror(TITLE, "Choose both folders first."); return
        src, out = os.path.abspath(self.src.get()), os.path.abspath(self.out.get())
        if not os.path.isdir(src):
            messagebox.showerror(TITLE, "The encrypted files folder doesn't exist."); return
        self.running = True; self.paused.clear(); self.stopping.clear()
        self.start_btn.config(state="disabled"); self.pause_btn.config(state="normal", text="Pause")
        self.stop_btn.config(state="normal")
        threading.Thread(target=self.run, args=(src, out, int(self.workers.get()), self.grey.get(), self.videos.get()), daemon=True).start()

    def toggle_pause(self):
        if self.paused.is_set(): self.paused.clear(); self.pause_btn.config(text="Pause")
        else: self.paused.set(); self.pause_btn.config(text="Resume")

    def stop(self):
        self.stopping.set(); self.paused.clear()
        self.pause_btn.config(state="disabled"); self.stop_btn.config(state="disabled")
        self.status.set("Stopping… finishing photos already in progress")

    def on_close(self):
        if self.running and not messagebox.askyesno(
                TITLE, "Recovery is running. Stop and close?\nProgress is saved; Start again later to resume."):
            return
        self.stopping.set(); self.paused.clear()
        self.root.after(400, self.root.destroy)

    # ---------- background run ----------
    def run(self, src, out, workers, grey="keep", videos=True):
        ev = self.events.put
        s = self.settings_for_run(src)
        os.makedirs(out, exist_ok=True)
        if not os.path.exists(s.library_path):
            ev(("status", "Learning camera settings from healthy photos (first run only)…"))
            entries = engine.scan_library(s.donor_roots(), [out.lower(), s.data_dir.lower()] + [d.lower() for d in s.skip_dirs],
                                          progress=lambda n: ev(("detail", f"{n} healthy photos read…")))
            os.makedirs(s.data_dir, exist_ok=True)
            with open(s.library_path, "w", encoding="utf-8") as fh: json.dump(entries, fh)
            ev(("detail", f"Camera library: {len(entries)} camera/size types"))
        if videos and not os.path.exists(s.video_refs_path):
            ev(("status", "Learning video settings from healthy videos (first run only)…"))
            added, total = video_index.update_ref_library(s.video_refs_path, s.donor_roots(),
                                                          [out.lower(), s.data_dir.lower()] + [d.lower() for d in s.skip_dirs])
            ev(("detail", f"Reference videos: {total} video settings types"))
        state_path = os.path.join(out, "progress.json")
        try:
            state = json.load(open(state_path, encoding="utf-8"))
        except Exception:
            state = {}
        ev(("status", "Listing encrypted files…"))
        files, out_low = [], out.lower()
        skip = [d.lower() for d in s.skip_dirs] + [s.data_dir.lower()]
        for dp, dns, fs in os.walk(src):
            low = dp.lower()
            if low.startswith(out_low) or any(k in low for k in skip):
                dns[:] = []; continue
            exts = PHOTO_EXT + (tuple(e + ".coot" for e in video.VIDEO_EXT) if videos else ())
            files += [os.path.join(dp, f) for f in fs if f.lower().endswith(exts)]
        files.sort()

        def outdated(r):
            # repaired by an older engine with a method that has since improved, or with a
            # different grey-area choice (only photos that have a grey area are redone)
            if r.get("method") not in engine.REDO_METHODS:
                return False
            if r.get("kind") == "video":  # videos: only retry failures after an engine update
                return r.get("status") == "failed" and r.get("ver") != engine.ENGINE_VERSION
            return r.get("ver") != engine.ENGINE_VERSION or (r.get("status") != "failed" and r.get("grey", "keep") != grey)

        todo = [f for f in files if os.path.relpath(f, src) not in state or outdated(state[os.path.relpath(f, src)])]
        redo = sum(1 for f in files if os.path.relpath(f, src) in state and outdated(state[os.path.relpath(f, src)]))
        current = {k: v for k, v in state.items() if not outdated(v)}
        ev(("init", len(files), len(files) - len(todo), current, workers, redo))

        t0, done_now, pending, it, unsaved, exhausted = time.time(), 0, set(), iter(todo), 0, False

        def save():
            tmp = state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh: json.dump(state, fh)
            os.replace(tmp, state_path)

        with ProcessPoolExecutor(workers, initializer=_init_worker, initargs=(dataclasses.asdict(s),)) as ex:
            while True:
                while not self.paused.is_set() and not self.stopping.is_set() and len(pending) < workers:
                    free = safety.free_ram_gb()
                    if free < s.min_free_ram_gb:
                        ev(("detail", f"Waiting for free memory ({free:.1f} GB free, need {s.min_free_ram_gb:.0f} GB)…"))
                        break
                    f = next(it, None)
                    if f is None:
                        exhausted = True; break
                    prev = state.get(os.path.relpath(f, src))
                    pending.add(ex.submit(_work, f, src, out, prev, grey))
                if not pending:
                    if self.stopping.is_set() or exhausted: break
                    if self.paused.is_set():
                        ev(("paused",)); time.sleep(0.3); continue
                    time.sleep(1.0); continue  # waiting for free RAM
                finished, pending = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)
                for fu in finished:
                    try: r = fu.result()
                    except Exception as exc: r = dict(file="?", status="failed", detail=f"crash: {exc}")
                    state[r["file"]] = r; done_now += 1; unsaved += 1
                    if unsaved >= SAVE_EVERY: save(); unsaved = 0
                    rate = (time.time() - t0) / done_now
                    ev(("result", r, rate * max(0, len(todo) - done_now)))
                if self.paused.is_set() and pending:
                    ev(("pausing", len(pending)))
        save()
        with open(os.path.join(out, "report.csv"), "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["file", "status", "method", "percent_recovered", "quality", "size", "grey_area",
                        "detail_or_output", "cropped_copy"])
            for k in sorted(state):
                r = state[k]
                w.writerow([k, r["status"], r.get("method", ""), r.get("percent", ""), r.get("quality", ""),
                            r.get("dims", ""), r.get("grey_note", ""), r.get("output", r.get("detail", "")),
                            r.get("cropped_output") or ""])
        finished_all = len(state) >= len(files)
        ev(("done", "Finished." if finished_all else "Stopped — press Start to resume."))

    # ---------- UI updates ----------
    def poll(self):
        try:
            while True: self.handle(self.events.get_nowait())
        except queue.Empty:
            pass
        self.root.after(150, self.poll)

    def handle(self, e):
        kind = e[0]
        if kind == "status":
            self.status.set(e[1])
        elif kind == "detail":
            self.detail.set(e[1])
        elif kind == "copies_done":
            self.copies_btn.config(state="normal")
            self.detail.set("")
            self.show_copies_result(e[1])
        elif kind == "init":
            _, total, already, state, workers, redo = e
            self.total, self.done = total, already
            self.counts = {"ok": 0, "review": 0, "failed": 0}; self.methods = {}
            for r in state.values(): self.count(r)
            self.progress.config(maximum=max(1, total), value=already)
            self.log.insert("end", f"{total} encrypted files, {already} done in an earlier run, {workers} workers")
            if redo:
                self.log.insert("end", f"{redo} photos from an earlier run will be redone with the improved engine {engine.ENGINE_VERSION}")
            self.update_status("")
        elif kind == "result":
            r, eta = e[1], e[2]
            self.done += 1; self.count(r); self.progress.config(value=self.done)
            extra = f"{r['method']} · {r['percent']}%" if r["status"] != "failed" else r["detail"]
            self.log.insert("end", f"{ICONS[r['status']]} {r['file']}  —  {extra}"); self.log.see("end")
            if r["status"] == "failed": self.log.itemconfig("end", fg="#b00020")
            elif r["status"] == "review": self.log.itemconfig("end", fg="#a15c00")
            if self.log.size() > 3000: self.log.delete(0, 500)
            if "output" in r and r.get("kind") != "video": self.show_preview(r["output"])
            self.detail.set("")
            self.update_status(f" · about {self.fmt(eta)} left" if not self.paused.is_set() else "")
        elif kind == "pausing":
            self.update_status(f" · pausing, finishing {e[1]} in progress…")
        elif kind == "paused":
            self.update_status(" · PAUSED — press Resume")
        elif kind == "done":
            self.running = False
            self.start_btn.config(state="normal", text="Start / Resume")
            self.pause_btn.config(state="disabled", text="Pause"); self.stop_btn.config(state="disabled")
            self.update_status(" · " + e[1]); self.log.insert("end", e[1]); self.log.see("end")

    def count(self, r):
        self.counts[r["status"]] = self.counts.get(r["status"], 0) + 1
        if r.get("method"): self.methods[r["method"]] = self.methods.get(r["method"], 0) + 1

    def update_status(self, suffix):
        c = self.counts
        m = ", ".join(f"{k} {v}" for k, v in sorted(self.methods.items(), key=lambda kv: -kv[1]))
        self.status.set(f"{self.done} / {self.total}  ·  {c.get('ok', 0)} recovered  ·  {c.get('review', 0)} need review  ·  "
                        f"{c.get('failed', 0)} failed{suffix}")
        if m: self.detail.set(f"by method: {m}")

    def show_preview(self, path):
        try:
            from PIL import Image, ImageTk
            im = Image.open(path); im.draft("RGB", (280, 380)); im.thumbnail((260, 360))
            self.preview_img = ImageTk.PhotoImage(im)
            self.preview.config(image=self.preview_img, text="")
        except Exception:
            pass

    @staticmethod
    def fmt(sec):
        sec = int(sec)
        if sec >= 3600: return f"{sec // 3600}h {sec % 3600 // 60:02d}m"
        return f"{sec // 60}m {sec % 60:02d}s" if sec >= 60 else f"{sec}s"


def _init_worker(settings_dict):
    from . import worker; worker.init(settings_dict)


def _work(path, src, out, prev=None, grey="keep"):
    from . import worker; return worker.work(path, src, out, prev, grey)


def main():
    settings = config.load()
    if settings.low_priority:
        safety.low_priority(background=False)
    safety.use_temp_dir(settings.temp_dir)
    root = tk.Tk()
    App(root, settings)
    root.mainloop()
