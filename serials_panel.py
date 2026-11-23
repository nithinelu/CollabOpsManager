"""Phone Serials tab - serial numbers, MACs and models read from the Cisco IP phones' own web pages,
optionally with the phone list discovered from CUCM over RisPort70. Formerly the separate
Cisco IP Phone Serial Grabber; grabber_engine does the work.

The results and a running scan live in host.serials_state, not in the panel, because a
language switch rebuilds the window (and this panel) while a scan may still be running.
"""

import os
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

import grabber_engine as E
from i18n import _, en

APP = "Collab Ops Manager"
STATUSES = [("Registered", "Registered phones only"), ("Any", "All phones")]   # (RisPort value, label)
TAGS = {E.ST_OK: "ok", E.ST_PARTIAL: "partial", E.ST_NOWEB: "bad", E.ST_ERROR: "bad"}
INK, AMBER, RED, MUTED, STRIPE = "#1F2937", "#B26A00", "#C62828", "#6B7280", "#F7F9FC"


def new_state(cfg):
    return {"targets": cfg.get("serials", {}).get("targets", ""), "results": [], "extra": {},
            "pending": [], "lock": threading.Lock(), "flush_queued": False, "progress": (0, 0),
            "running": False, "discovering": False, "stop": threading.Event(), "message": None}


def saved_settings(host):
    """What config.json keeps for this tab. The phone web password is never saved."""
    def num(var, kind, default):
        try:
            return kind(var.get())
        except (ValueError, tk.TclError):
            return default
    return {"targets": host.serials_state["targets"][:200000], "node": host.v_ser_node.get().strip(),
            "status": host.v_ser_status.get(), "workers": num(host.v_ser_workers, int, 64),
            "timeout": num(host.v_ser_timeout, float, 4.0), "https": bool(host.v_ser_https.get()),
            "phone_user": host.v_ser_puser.get().strip()}


def _later(host, method, *a):
    """Run a panel method on the UI thread, on whichever panel is showing by then."""
    def go():
        panel = getattr(host, "serials_panel", None)
        if panel is not None and panel.winfo_exists():
            getattr(panel, method)(*a)
    host.ui(go)


def _ip_key(r):
    try:
        return 0, tuple(int(p) for p in r["ip"].split("."))
    except ValueError:
        return 1, r["ip"]


class SerialsPanel(ttk.Frame):
    def __init__(self, parent, host):
        super().__init__(parent)
        self.host = host
        self.st = host.serials_state
        self.sort_col, self.sort_rev = None, False
        self._row_map = {}
        self._count_job = None
        self._build()
        self._show_busy()
        self._show_progress()
        self.refresh_tree()

    # ------------------------------------------------------------------ layout
    def _build(self):
        """Targets | CUCM discovery | scan options in one row, then the action bar, then the results.
        Columns and button order are mirrored in Arabic."""
        h = self.host
        foot = ttk.Frame(self)
        foot.pack(side="bottom", fill="x", pady=(6, 0))
        self.pb = ttk.Progressbar(foot, mode="determinate", length=160)
        self.pb.pack(side=h.S)
        self.lbl_prog = ttk.Label(foot, text="", style="Muted.TLabel")
        self.lbl_prog.pack(side=h.S, padx=8)
        ttk.Label(foot, text=_("Phones need 'Web Access' enabled in CUCM."),
                  style="Muted.TLabel").pack(side=h.E)

        band = ttk.Frame(self)
        band.pack(fill="x")
        for n, build in enumerate((self._build_targets, self._build_cucm, self._build_scan)):
            box = build(band)
            box.grid(row=0, column=h.col(n), sticky="nsew",
                     padx=(0, 0) if n == 0 else ((8, 0) if not h.rtl else (0, 8)))
        band.columnconfigure(h.col(0), weight=1, minsize=330)

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=8)
        self.btn_start = ttk.Button(bar, text=_("▶  Grab serials"), style="Accent.TButton", command=self.start)
        self.btn_start.pack(side=h.S)
        self.btn_stop = ttk.Button(bar, text=_("Stop"), command=self.stop)
        self.btn_stop.pack(side=h.S, padx=6)
        for text, cmd in (("Export Excel", lambda: self.export("xlsx")), ("Export CSV", lambda: self.export("csv")),
                          ("Copy serials", self.copy_serials), ("Clear results", self.clear_results)):
            ttk.Button(bar, text=_(text), command=cmd).pack(side=h.E, padx=(6, 0) if not h.rtl else (0, 6))
        self._build_results(self)

    def _build_targets(self, parent):
        h = self.host
        box = ttk.LabelFrame(parent, text=_("Targets"), padding=8)
        ttk.Label(box, text=_("IP addresses, ranges or subnets,\nsuch as 10.1.1.10-50 or 10.1.1.0/24"),
                  style="Muted.TLabel", justify=h.J).pack(anchor=h.W)
        row = ttk.Frame(box)
        row.pack(side="bottom", fill="x", pady=(4, 0))
        ttk.Button(row, text=_("Load file…"), command=self.load_file).pack(side=h.S)
        ttk.Button(row, text=_("Clear"), command=self.clear_targets).pack(side=h.S, padx=4)
        self.lbl_count = ttk.Label(box, text="", style="Muted.TLabel")
        self.lbl_count.pack(side="bottom", anchor=h.W, pady=(2, 0))
        tf = ttk.Frame(box)
        tf.pack(fill="both", expand=True, pady=(4, 0))
        self.t_targets = tk.Text(tf, height=5, width=30, font=("Consolas", 10), relief="flat", undo=True,
                                 highlightthickness=1, highlightbackground="#D6DDE6", highlightcolor="#0E7C86")
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.t_targets.yview)
        self.t_targets.configure(yscrollcommand=sb.set)
        self.t_targets.pack(side=h.S, fill="both", expand=True)
        sb.pack(side=h.E, fill="y")
        self.t_targets.insert("1.0", self.st["targets"])
        self.t_targets.edit_modified(False)
        self.t_targets.bind("<<Modified>>", self._targets_changed)
        self._count_targets()
        return box

    def _build_cucm(self, parent):
        h = self.host
        box = ttk.LabelFrame(parent, text=_("Discover from CUCM (optional)"), padding=8)
        g = ttk.Frame(box)
        g.pack(fill="x")
        ttk.Label(g, text=_("CUCM node")).grid(row=0, column=h.col(0, last=1), sticky=h.W, pady=2, padx=(0, 6))
        self.c_node = ttk.Combobox(g, textvariable=h.v_ser_node, width=27, values=h.node_choices("cucm"))
        self.c_node.grid(row=0, column=h.col(1, last=1), sticky="we", pady=2)
        ttk.Label(g, text=_("Phones")).grid(row=1, column=h.col(0, last=1), sticky=h.W, pady=2, padx=(0, 6))
        self.c_status = ttk.Combobox(g, values=[_(label) for _v, label in STATUSES], state="readonly", width=24)
        self.c_status.set(_(dict(STATUSES).get(h.v_ser_status.get(), STATUSES[0][1])))
        self.c_status.bind("<<ComboboxSelected>>", self._status_picked)
        self.c_status.grid(row=1, column=h.col(1, last=1), sticky=h.W, pady=2)
        g.columnconfigure(h.col(1, last=1), weight=1)
        self.btn_cucm = ttk.Button(box, text=_("Discover phones (RisPort)"), command=self.discover)
        self.btn_cucm.pack(anchor=h.W, pady=(6, 0))
        ttk.Label(box, text=_("Uses the AXL user on the Cluster tab.\n"
                              "Adds each phone's IP to the targets,\n"
                              "with its device name, DN and description."),
                  style="Muted.TLabel", justify=h.J).pack(anchor=h.W, pady=(4, 0))
        return box

    def _build_scan(self, parent):
        h = self.host
        box = ttk.LabelFrame(parent, text=_("Scan"), padding=8)
        g = ttk.Frame(box)
        g.pack(fill="x")
        for n, (label, var, lo, hi, step) in enumerate((("Parallel", h.v_ser_workers, 1, 256, 16),
                                                        ("Timeout (s)", h.v_ser_timeout, 1, 30, 1))):
            ttk.Label(g, text=_(label)).grid(row=0, column=h.col(2 * n, last=3), sticky=h.W, padx=(0, 4))
            ttk.Spinbox(g, from_=lo, to=hi, increment=step, textvariable=var, width=5).grid(
                row=0, column=h.col(2 * n + 1, last=3), sticky=h.W, padx=(0, 12) if not h.rtl else (12, 0))
        ttk.Checkbutton(box, text=_("Also try HTTPS (port 443)"), variable=h.v_ser_https).pack(anchor=h.W, pady=(4, 0))
        ttk.Label(box, text=_("Phone web login, if the pages ask for one:"),
                  style="Muted.TLabel").pack(anchor=h.W, pady=(4, 0))
        login = ttk.Frame(box)
        login.pack(fill="x")
        h._row(login, 0, "Phone web user", h.v_ser_puser, width=16, last=1)
        h._row(login, 1, "Phone web password", h.v_ser_ppw, show="•", width=16, last=1)
        return box

    def _build_results(self, parent):
        h = self.host
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text=_("Results"), style="Head.TLabel").pack(side=h.S)
        self.lbl_stats = ttk.Label(top, text="")
        self.lbl_stats.pack(side=h.S, padx=14)
        ttk.Checkbutton(top, text=_("Phones only"), variable=h.v_ser_only_ok,
                        command=self.refresh_tree).pack(side=h.E)
        ttk.Entry(top, textvariable=h.v_ser_filter, width=22).pack(side=h.E, padx=(4, 12) if not h.rtl else (12, 4))
        ttk.Label(top, text=_("Filter")).pack(side=h.E)
        h.v_ser_filter.trace_add("write", lambda *a: self.refresh_tree())

        fr = ttk.Frame(parent)
        fr.pack(fill="both", expand=True)
        cols = [k for k, _h, _w in E.COLUMNS]
        self.tv = ttk.Treeview(fr, columns=cols, show="headings", selectmode="extended", height=6)
        for k, head, w in E.COLUMNS:
            self.tv.heading(k, text=_(head), command=lambda k=k: self.sort_by(k))
            self.tv.column(k, width=w, anchor=h.W, stretch=(k == "note"))
        h.mirror(self.tv)
        ys = ttk.Scrollbar(fr, orient="vertical", command=self.tv.yview)
        xs = ttk.Scrollbar(fr, orient="horizontal", command=self.tv.xview)
        self.tv.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tv.grid(row=0, column=h.col(0, last=1), sticky="nsew")
        ys.grid(row=0, column=h.col(1, last=1), sticky="ns")
        xs.grid(row=1, column=h.col(0, last=1), sticky="ew")
        fr.rowconfigure(0, weight=1)
        fr.columnconfigure(h.col(0, last=1), weight=1)
        if h.rtl:   # mirrored columns: start at the right-hand end, where the IP address is
            self.tv.bind("<Map>", lambda e: self.after(50, lambda: self.tv.xview_moveto(1.0)), add="+")
        self.tv.tag_configure("odd", background=STRIPE)
        self.tv.tag_configure("ok", foreground=INK)
        self.tv.tag_configure("partial", foreground=AMBER)
        self.tv.tag_configure("bad", foreground=RED)
        self.tv.tag_configure("dim", foreground=MUTED)
        self.tv.bind("<Control-c>", lambda e: self.copy_rows())
        self.tv.bind("<Button-3>", self._menu)
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label=_("Copy selected rows"), command=self.copy_rows)
        self.menu.add_command(label=_("Copy serial"), command=lambda: self.copy_field("serial"))
        self.menu.add_command(label=_("Copy MAC"), command=lambda: self.copy_field("mac"))
        self.menu.add_separator()
        self.menu.add_command(label=_("Open phone web page"), command=self.open_web)
        self.menu.add_command(label=_("Re-scan selected"), command=self.rescan_selected)

    # ------------------------------------------------------------------ small helpers
    def _status_picked(self, _e=None):
        label = self.c_status.get()
        self.host.v_ser_status.set(next(v for v, lab in STATUSES if _(lab) == label))

    def _message(self, key, **kw):
        """Status line under the tab, kept as its English key so a language switch can translate it."""
        self.st["message"] = (key, kw)
        self._show_message()

    def _message_raw(self, text):
        """Status line text that has no translation (CUCM discovery progress from the engine)."""
        self.st["message"] = (None, {"text": text})
        self._show_message()

    def _show_message(self):
        key, kw = self.st["message"] or ("Idle", {})
        if key is None:
            text = kw["text"]
        else:
            text = _(key, **{k: _(v) if k == "status" else v for k, v in kw.items()})
        self.lbl_prog.configure(text=text)

    def _show_progress(self):
        done, total = self.st["progress"]
        self.pb.configure(maximum=max(total, 1), value=done)
        self._show_message()

    def _show_busy(self):
        busy = self.st["running"] or self.st["discovering"]
        self.btn_start.state(["disabled"] if busy else ["!disabled"])
        self.btn_cucm.state(["disabled"] if busy else ["!disabled"])
        self.btn_stop.state(["!disabled"] if self.st["running"] else ["disabled"])

    # ------------------------------------------------------------------ targets
    def _targets_changed(self, _e=None):
        self.t_targets.edit_modified(False)
        self.st["targets"] = self.t_targets.get("1.0", "end-1c")
        if self._count_job:
            self.after_cancel(self._count_job)
        self._count_job = self.after(300, self._count_targets)

    def _count_targets(self):
        self._count_job = None
        targets, errs = E.parse_targets(self.t_targets.get("1.0", "end"))
        text = _("{n} addresses", n=f"{len(targets):,}")
        if errs:
            text += "  ·  " + _("{n} invalid", n=len(errs))
        self.lbl_count.configure(text=text, foreground=RED if errs else MUTED)

    def _append_targets(self, text):
        cur = self.t_targets.get("1.0", "end").strip()
        self.t_targets.delete("1.0", "end")
        self.t_targets.insert("1.0", (cur + "\n" if cur else "") + text.strip() + "\n")
        self._targets_changed()

    def load_file(self):
        p = filedialog.askopenfilename(title=_("Load targets"), filetypes=[
            (_("Target lists"), "*.txt *.csv *.xlsx *.xlsm"), (_("All files"), "*.*")])
        if not p:
            return
        try:
            text = E.read_target_file(p)
        except Exception as e:  # noqa: BLE001 - any unreadable file
            messagebox.showerror(APP, _("Could not read {path}:\n{err}", path=p, err=e))
            return
        if not text.strip():
            messagebox.showwarning(APP, _("No IP addresses, ranges or subnets found in that file."))
            return
        self._append_targets(text)

    def clear_targets(self):
        self.t_targets.delete("1.0", "end")
        self.st["extra"] = {}
        self._targets_changed()

    # ------------------------------------------------------------------ CUCM discovery
    def discover(self):
        h, st = self.host, self.st
        node = h.node_address(h.v_ser_node.get())
        user, pw = h.v_axluser.get().strip(), h.v_axlpw.get()
        if not (node and user and pw):
            messagebox.showwarning(APP, _("Pick a CUCM node, and enter the AXL user and password on the Cluster tab."))
            return
        if st["running"] or st["discovering"]:
            return
        st["discovering"] = True
        self._show_busy()
        self._message("Asking {host} for phones…", host=node)
        status = h.v_ser_status.get()
        h.log(en("Phone serials: asking {host} for its phones over RisPort ({status})", host=node, status=status))

        def run():
            try:
                devs = E.cucm_discover(node, user, pw, status=status, log=lambda m: _later(h, "_message_raw", m))
            except Exception as e:  # noqa: BLE001 - shown to the user
                _later(h, "_discover_failed", node, str(e))
                return
            _later(h, "_discover_done", node, devs)

        threading.Thread(target=run, daemon=True).start()

    def _discover_failed(self, node, err):
        self.st["discovering"] = False
        self._show_busy()
        self._message("CUCM discovery failed")
        self.host.log(en("Phone serials: discovery on {host} failed: {err}", host=node, err=err))
        messagebox.showerror(APP, err)

    def _discover_done(self, node, devs):
        self.st["discovering"] = False
        self._show_busy()
        ips, no_ip, web_off = [], 0, 0
        for d in devs:
            if not d["ip"]:
                no_ip += 1
                continue
            ips.append(d["ip"])
            self.st["extra"][d["ip"]] = {"hostname": d["name"], "dn": d["dn"], "cucm_desc": d["desc"],
                                         "cucm_status": d["status"]}
            if d.get("httpd", "").lower() == "no":
                web_off += 1
        if ips:
            self._append_targets("\n".join(ips))
        self.host.log(en("Phone serials: {host} returned {n} phones, {k} with an IP address",
                         host=node, n=len(devs), k=len(ips)))
        first = ("CUCM returned {n} phones; {k} IP addresses were added to the targets.", {"n": len(devs), "k": len(ips)})
        lines = [_(first[0], **first[1])]
        if no_ip:
            lines.append(_("{n} had no IP address, because they are not registered.", n=no_ip))
        if web_off:
            lines.append(_("{n} have their web server turned off: enable 'Web Access' on those phones.", n=web_off))
        self._message(first[0], **first[1])
        messagebox.showinfo(APP, "\n".join(lines))

    # ------------------------------------------------------------------ scan
    def _opts(self):
        h = self.host
        try:
            workers = max(1, min(256, int(h.v_ser_workers.get())))
            timeout = max(0.5, min(60.0, float(h.v_ser_timeout.get())))
        except (ValueError, tk.TclError):
            raise ValueError(_("Parallel and timeout must be numbers."))
        user = h.v_ser_puser.get().strip()
        return workers, timeout, ((user, h.v_ser_ppw.get()) if user else None)

    def start(self, targets=None):
        h, st = self.host, self.st
        if st["running"] or st["discovering"]:
            return
        if targets is None:
            targets, errs = E.parse_targets(self.t_targets.get("1.0", "end"))
            if errs:
                bad = "\n".join(errs[:10]) + ("\n…" if len(errs) > 10 else "")
                if not messagebox.askyesno(APP, _("These entries are not valid and will be skipped:\n\n{bad}\n\n"
                                                  "Continue with {n} addresses?", bad=bad, n=len(targets))):
                    return
            if not targets:
                messagebox.showwarning(APP, _("Add some IP addresses, ranges or subnets first."))
                return
        try:
            workers, timeout, auth = self._opts()
        except ValueError as e:
            messagebox.showerror(APP, str(e))
            return
        h._save_cfg()
        wanted = set(targets)               # a new scan replaces earlier results for the same addresses
        st["results"] = [r for r in st["results"] if r["ip"] not in wanted]
        st["stop"] = stop = threading.Event()
        st["running"], st["progress"] = True, (0, len(targets))
        self.refresh_tree()
        self._show_busy()
        self._show_progress()
        self._message("Scanning {n} addresses…", n=f"{len(targets):,}")
        h.log(en("Phone serials: scanning {n} addresses", n=len(targets)))
        https, extra = bool(h.v_ser_https.get()), dict(st["extra"])

        def on_result(r, done, total):        # worker threads
            with st["lock"]:
                st["pending"].append(r)
                st["progress"] = (done, total)
                queue_flush, st["flush_queued"] = not st["flush_queued"], True
            if queue_flush:
                _later(h, "_flush")

        def run():
            err = ""
            try:
                E.scan(targets, workers=workers, timeout=timeout, try_https=https, auth=auth,
                       stop_event=stop, extra=extra, on_result=on_result)
            except Exception as e:  # noqa: BLE001 - reported, the scan just ends
                err = str(e)
            _later(h, "_scan_done", stop.is_set(), err)

        threading.Thread(target=run, daemon=True).start()

    def _flush(self):
        st = self.st
        with st["lock"]:
            new, st["pending"], st["flush_queued"] = st["pending"], [], False
        if not new:
            return
        st["results"].extend(new)
        done, total = st["progress"]
        last = new[-1]
        self._message("{done} / {total}  ·  last: {ip}  {status}", done=f"{done:,}", total=f"{total:,}",
                      ip=last["ip"], status=last["status"])
        self.pb.configure(maximum=max(total, 1), value=done)
        self.refresh_tree()

    def _scan_done(self, stopped, err):
        self._flush()
        st = self.st
        st["running"] = False
        ok = sum(1 for r in st["results"] if r["status"] == E.ST_OK)
        self._show_busy()
        if err:
            self._message("Scan failed: {err}", err=err)
            self.host.log(en("Phone serials: scan failed: {err}", err=err))
            return
        self._message("Stopped  ·  {n} serial numbers read" if stopped
                      else "Finished  ·  {n} serial numbers read", n=ok)
        self.host.log(en("Phone serials: {how}, {n} serial numbers read, {t} addresses in the results",
                         how="stopped" if stopped else "finished", n=ok, t=len(st["results"])))

    def stop(self):
        if self.st["running"]:
            self.st["stop"].set()
            self._message("Stopping, finishing the requests already sent…")

    # ------------------------------------------------------------------ results
    def _visible(self):
        h = self.host
        f = h.v_ser_filter.get().strip().lower()
        rows = self.st["results"]
        if h.v_ser_only_ok.get():
            rows = [r for r in rows if r["status"] in (E.ST_OK, E.ST_PARTIAL)]
        if f:
            rows = [r for r in rows if f in _(r.get("status", "")).lower() or
                    any(f in str(r.get(k, "")).lower() for k, _h, _w in E.COLUMNS)]
        if self.sort_col == "ip":
            return sorted(rows, key=_ip_key, reverse=self.sort_rev)
        if self.sort_col:
            k = self.sort_col
            return sorted(rows, key=lambda r: str(r.get(k, "")).lower(), reverse=self.sort_rev)
        return sorted(rows, key=lambda r: ({E.ST_OK: 0, E.ST_PARTIAL: 1}.get(r["status"], 2), _ip_key(r)))

    def refresh_tree(self):
        self.tv.delete(*self.tv.get_children())
        self._row_map = {}
        for i, r in enumerate(self._visible()):
            tag = TAGS.get(r.get("status"), "dim")
            values = [_(r.get(k, "")) if k == "status" else r.get(k, "") for k, _h, _w in E.COLUMNS]
            iid = self.tv.insert("", "end", values=values, tags=(tag, "odd") if i % 2 else (tag,))
            self._row_map[iid] = r
        results = self.st["results"]
        counts = {}
        for r in results:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        models = len({r.get("model") for r in results if r["status"] == E.ST_OK and r.get("model")})
        parts = [_("{n} serials", n=counts.get(E.ST_OK, 0)), _("{n} models", n=models)]
        parts += [f"{_(s)}: {counts[s]}" for s in (E.ST_PARTIAL, E.ST_NOWEB, E.ST_NOTPHONE, E.ST_DOWN, E.ST_ERROR)
                  if counts.get(s)]
        self.lbl_stats.configure(text="   ·   ".join(parts) if results else "")

    def sort_by(self, k):
        self.sort_rev = (not self.sort_rev) if self.sort_col == k else False
        self.sort_col = k
        self.refresh_tree()

    def _selected(self):
        return [self._row_map[i] for i in self.tv.selection() if i in self._row_map]

    def _menu(self, e):
        iid = self.tv.identify_row(e.y)
        if iid and iid not in self.tv.selection():
            self.tv.selection_set(iid)
        if self.tv.selection():
            self.menu.tk_popup(e.x_root, e.y_root)

    def _clip(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)

    def copy_rows(self):
        rows = self._selected()
        if rows:
            lines = ["\t".join(head for _k, head, _w in E.COLUMNS)]
            lines += ["\t".join(str(r.get(k, "")) for k, _h, _w in E.COLUMNS) for r in rows]
            self._clip("\n".join(lines))

    def copy_field(self, k):
        vals = [str(r.get(k, "")) for r in self._selected() if r.get(k)]
        if vals:
            self._clip("\n".join(vals))

    def copy_serials(self):
        rows = [r for r in self._visible() if r.get("serial")]
        if not rows:
            messagebox.showinfo(APP, _("No serial numbers to copy yet."))
            return
        self._clip("\n".join(f"{r['serial']}\t{r.get('model', '')}\t{r.get('mac', '')}\t{r['ip']}" for r in rows))
        self._message("Copied {n} serials: serial, model, MAC and IP, separated by tabs.", n=len(rows))

    def open_web(self):
        for r in self._selected()[:5]:
            scheme = "https" if r.get("source", "").startswith("https") else "http"
            webbrowser.open(f"{scheme}://{r['ip']}/")

    def rescan_selected(self):
        ips = [r["ip"] for r in self._selected()]
        if ips:
            self.start(ips)

    def clear_results(self):
        if self.st["results"] and not self.st["running"] and messagebox.askyesno(APP, _("Clear all results?")):
            self.st["results"] = []
            self.st["progress"] = (0, 0)
            self._show_progress()
            self.refresh_tree()

    def export(self, kind):
        rows = self._visible()
        if not rows:
            messagebox.showinfo(APP, _("Nothing to export yet."))
            return
        ext = ".xlsx" if kind == "xlsx" else ".csv"
        p = filedialog.asksaveasfilename(title=_("Export"), defaultextension=ext,
                                         initialfile=f"IP_Phone_Serials{ext}",
                                         filetypes=[("Excel", "*.xlsx")] if kind == "xlsx" else [("CSV", "*.csv")])
        if not p:
            return
        try:
            (E.export_xlsx if kind == "xlsx" else E.export_csv)(rows, p)
        except PermissionError:
            messagebox.showerror(APP, _("Cannot write {path}. Is it open in Excel?", path=p))
            return
        except Exception as e:  # noqa: BLE001 - shown to the user
            messagebox.showerror(APP, _("Export failed:\n{err}", err=e))
            return
        self._message("Exported {n} rows to {file}", n=len(rows), file=os.path.basename(p))
        self.host.log(en("Phone serials: exported {n} rows to {path}", n=len(rows), path=p))
        if messagebox.askyesno(APP, _("Exported {n} rows.\n\nOpen the file now?", n=len(rows))):
            os.startfile(p)
