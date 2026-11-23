"""Phone Backgrounds tab - pictures resized for Cisco 79XX / 88XX / 98XX phones, with each model's
thumbnails and List.xml, saved to a folder or ZIP or uploaded to the CUCM TFTP servers
(phone_backgrounds does the work).

The picture list lives in host.bg_state and the choices in host.v_bg_* variables, so a language
switch (which rebuilds this panel) keeps them. Uploads run through host.task, which blocks a
language switch until they finish.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import phone_backgrounds as B
from cucm_cli import CLIError
from i18n import _

APP = "Collab Ops Manager"
FITS = [("fill", "Fill the screen (cut the edges)"), ("fit", "Show the whole picture (black bars)")]
THEMES = [("light", "Light"), ("dark", "Dark")]
PREVIEW, THUMB_BOX = (200, 80), (100, 80)     # preview sizes that fit at the default window size, both languages
SERIES_HEAD = {"79XX": "Cisco IP Phone 79XX", "88XX": "Cisco IP Phone 88XX",
               "PhoneOS": "PhoneOS: Desk Phone 98XX, 8875"}


def new_state(cfg):
    s = cfg.get("backgrounds", {})
    pics = [p for p in s.get("pictures", []) if isinstance(p, dict) and p.get("path") and p.get("name")]
    return {"pictures": pics, "message": None, "version": int(s.get("list_version", 0) or 0),
            "logo": s.get("logo") or None}


def saved_settings(host):
    st = host.bg_state
    return {"pictures": st["pictures"][:100], "logo": st.get("logo"), "models": checked_models(host),
            "fit": host.v_bg_fit.get(),
            "restart": bool(host.v_bg_restart.get()), "keep": bool(host.v_bg_keep.get()),
            "list_version": st["version"]}


def model_var(host, key):
    return getattr(host, "v_bg_m_" + key)


def checked_models(host):
    return [m[0] for m in B.MODELS if model_var(host, m[0]).get()]


def make_vars(host, cfg):
    """The tab's tk variables on the App (v_* survive a language switch)."""
    s = cfg.get("backgrounds", {})
    chosen = set(s.get("models", ["8800", "9861", "9871"]))
    for m in B.MODELS:
        setattr(host, "v_bg_m_" + m[0], tk.BooleanVar(value=m[0] in chosen))
    host.v_bg_fit = tk.StringVar(value=s.get("fit", "fill") if s.get("fit") in ("fill", "fit") else "fill")
    host.v_bg_restart = tk.BooleanVar(value=s.get("restart", True))
    host.v_bg_keep = tk.BooleanVar(value=s.get("keep", True))
    host.v_bg_name = tk.StringVar()
    host.v_bg_preview = tk.StringVar()


class BackgroundsPanel(ttk.Frame):
    def __init__(self, parent, host, picker_class):
        super().__init__(parent)
        self.host = host
        self.picker_class = picker_class
        self.st = host.bg_state
        self._photos = []
        self._build()
        self.refresh_list()
        self._models_changed()
        self._show_message()

    # ------------------------------------------------------------------ layout
    def _build(self):
        h = self.host
        foot = ttk.Frame(self)
        foot.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Label(foot, style="Muted.TLabel", justify=h.J, text=_(
            "Users pick the picture on the phone (Settings › Wallpaper). CUCM must allow it: Common Phone Profile ›\n"
            "Enable End User Access to Phone Background Image Setting, or set Background Image = List.xml for all phones."
        )).pack(side=h.S)

        band = ttk.Frame(self)
        band.pack(fill="x")
        for n, build in enumerate((self._build_pictures, self._build_models, self._build_options)):
            box = build(band)
            box.grid(row=0, column=h.col(n), sticky="nsew", padx=(0, 0) if n == 0 else ((8, 0) if not h.rtl else (0, 8)))
        band.columnconfigure(h.col(0), weight=1, minsize=300)

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=8)
        ttk.Button(bar, text=_("⇪  Upload to TFTP servers"), style="Accent.TButton",
                   command=self.upload).pack(side=h.S)
        for text, cmd in (("Save as ZIP…", self.save_zip), ("Save to folder…", self.save_folder)):
            ttk.Button(bar, text=_(text), command=cmd).pack(side=h.E, padx=(6, 0) if not h.rtl else (0, 6))
        logo = ttk.Frame(bar)                         # PhoneOS logo: Name="logo" in List.xml, logo.png per folder
        logo.pack(side=h.E, padx=(0, 18) if not h.rtl else (18, 0))
        ttk.Label(logo, text=_("PhoneOS logo")).pack(side=h.S)
        self.lbl_logo = ttk.Label(logo, text="", style="Muted.TLabel", width=16)
        self.lbl_logo.pack(side=h.S, padx=6)
        ttk.Button(logo, text=_("Logo…"), command=self.choose_logo).pack(side=h.S)
        self.btn_nologo = ttk.Button(logo, text="✕", width=3, command=self.remove_logo)
        self.btn_nologo.pack(side=h.S, padx=(4, 0) if not h.rtl else (0, 4))
        self.lbl_msg = ttk.Label(bar, text="", style="Muted.TLabel")      # packed last: it gets what is left
        self.lbl_msg.pack(side=h.S, padx=10)
        self._show_logo()

        low = ttk.Frame(self)
        low.pack(fill="both", expand=True)
        prev = self._build_preview(low)
        prev.pack(side=h.S, fill="y")
        srv = ttk.LabelFrame(low, text=_("TFTP servers (CUCM nodes from the Cluster tab)"), padding=8)
        srv.pack(side=h.S, fill="both", expand=True, padx=(8, 0) if not h.rtl else (0, 8))
        ttk.Label(srv, style="Muted.TLabel", justify=h.J, text=_(          # packed first: the list shrinks, not the note
            "Upload: OS admin user; TFTP restart: AXL user (Cluster tab).\n"
            "Upload to every node that runs Cisco TFTP.")).pack(
            side="bottom", anchor=h.W, pady=(4, 0))
        self.picker = self.picker_class(srv, h, height=4,
                                 keep=lambda n: h.cluster_of(n["host"]) == "cucm" and n.get("type") != "IM&P")
        for c, w in (("sel", 30), ("host", 110), ("ip", 100), ("type", 55), ("role", 80), ("status", 160)):
            self.picker.tree.column(c, width=w)          # half-width box: all columns, status included, fit
        self.picker.pack(fill="both", expand=True)

    def _build_pictures(self, parent):
        h = self.host
        box = ttk.LabelFrame(parent, text=_("Pictures"), padding=8)
        trow = ttk.Frame(box)                          # bottom row: PhoneOS theme of the selected picture
        trow.pack(side="bottom", fill="x", pady=(4, 0))
        ttk.Label(trow, text=_("PhoneOS theme")).pack(side=h.S)
        self.c_theme = ttk.Combobox(trow, values=[_(t) for _v, t in THEMES], state="readonly", width=8)
        self.c_theme.pack(side=h.S, padx=4)
        self.c_theme.bind("<<ComboboxSelected>>", self._theme_picked)
        row = ttk.Frame(box)
        row.pack(side="bottom", fill="x", pady=(4, 0))
        ttk.Label(row, text=_("File name")).pack(side=h.S)
        e = ttk.Entry(row, textvariable=h.v_bg_name, width=14)
        e.pack(side=h.S, padx=4)
        e.bind("<Return>", self._rename)
        e.bind("<FocusOut>", self._rename)
        ttk.Button(row, text=_("Rename"), command=self._rename).pack(side=h.S)
        ttk.Button(row, text=_("Rename all…"), command=self.rename_all).pack(side=h.S, padx=4)
        btns = ttk.Frame(box)
        btns.pack(side="bottom", fill="x", pady=(4, 0))
        ttk.Button(btns, text=_("Add pictures…"), command=self.add_pictures).pack(side=h.S)
        ttk.Button(btns, text=_("Remove"), command=self.remove_picture).pack(side=h.S, padx=4)
        ttk.Button(btns, text=_("Clear"), command=self.clear_pictures).pack(side=h.S)
        lf = ttk.Frame(box)
        lf.pack(fill="both", expand=True)
        self.lb = tk.Listbox(lf, height=6, width=34, activestyle="none", exportselection=False, relief="flat",
                             highlightthickness=1, highlightbackground="#D6DDE6", highlightcolor="#0E7C86",
                             selectbackground="#0E7C86", font=("Segoe UI", 10), justify=h.J)
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.lb.yview)
        self.lb.configure(yscrollcommand=sb.set)
        self.lb.pack(side=h.S, fill="both", expand=True)
        sb.pack(side=h.E, fill="y")
        self.lb.bind("<<ListboxSelect>>", self._picked)
        self.e_name = e
        self.lb.bind("<Double-Button-1>", lambda ev: (e.focus_set(), e.select_range(0, "end")))
        return box

    def _build_models(self, parent):
        h = self.host
        box = ttk.LabelFrame(parent, text=_("Phone models"), padding=8)
        r = 0
        for series in B.SERIES:
            ttk.Label(box, text=_(SERIES_HEAD[series]), style="Head.TLabel").grid(
                row=r, column=h.col(0, span=2, last=1), columnspan=2, sticky=h.W, pady=(0 if r == 0 else 6, 0))
            r += 1
            slot = 0                                   # long labels take a whole row, short ones two per row
            for m in (m for m in B.MODELS if m[1] == series):
                cb = ttk.Checkbutton(box, text=m[2], variable=model_var(h, m[0]), command=self._models_changed)
                if len(m[2]) > 25:
                    if slot:
                        r, slot = r + 1, 0
                    cb.grid(row=r, column=h.col(0, span=2, last=1), columnspan=2, sticky=h.W)
                    r += 1
                else:
                    cb.grid(row=r, column=h.col(slot, last=1), sticky=h.W, padx=(0, 14) if not h.rtl else (14, 0))
                    r, slot = (r + 1, 0) if slot else (r, 1)
            r += 1 if slot else 0
        return box

    def _build_options(self, parent):
        h = self.host
        box = ttk.LabelFrame(parent, text=_("Options"), padding=8)
        ttk.Label(box, text=_("Picture shape differs from the screen:")).pack(anchor=h.W)
        for value, label in FITS:
            ttk.Radiobutton(box, text=_(label), value=value, variable=h.v_bg_fit,
                            command=self.show_preview).pack(anchor=h.W)
        ttk.Checkbutton(box, text=_("Restart Cisco TFTP after the upload\n(phones only see new files after it)"),
                        variable=h.v_bg_restart).pack(anchor=h.W, pady=(10, 0))
        ttk.Checkbutton(box, text=_("Keep what List.xml on the server lists, such as\n"
                                    "Cisco's default wallpapers, and add these after it"),
                        variable=h.v_bg_keep).pack(anchor=h.W, pady=(8, 0))
        return box

    def _build_preview(self, parent):
        h = self.host
        box = ttk.LabelFrame(parent, text=_("Preview"), padding=8)
        top = ttk.Frame(box)
        top.pack(fill="x")
        ttk.Label(top, text=_("Model")).pack(side=h.S)
        self.c_prev = ttk.Combobox(top, textvariable=h.v_bg_preview, state="readonly", width=17)
        self.c_prev.pack(side=h.S, padx=6)
        self.c_prev.bind("<<ComboboxSelected>>", lambda e: self.show_preview())
        self.lbl_sizes = ttk.Label(top, text="", style="Muted.TLabel")      # short lines: the box stays narrow
        self.lbl_sizes.pack(side=h.S)
        self.lbl_info = ttk.Label(box, text="", style="Muted.TLabel")       # TFTP path of the full picture
        self.lbl_info.pack(anchor=h.W, pady=(4, 2))
        imgs = ttk.Frame(box)
        imgs.pack(fill="x")
        self.lbl_full = tk.Label(imgs, bg="#111827", width=PREVIEW[0], height=PREVIEW[1])
        self.lbl_full.pack(side=h.S)
        self.lbl_thumb = tk.Label(imgs, bg="#111827")
        self.lbl_thumb.pack(side=h.S, padx=8, anchor="n")
        return box

    # ------------------------------------------------------------------ pictures
    def refresh_list(self, select=None):
        self.lb.delete(0, "end")
        for p in self.st["pictures"]:
            self.lb.insert("end", f"{p['name']}    ({os.path.basename(p['path'])})")
        n = len(self.st["pictures"])
        if n:
            i = select if select is not None and select < n else 0
            self.lb.selection_set(i)
            self.lb.see(i)
        self._picked()

    def _sel(self):
        s = self.lb.curselection()
        return s[0] if s else None

    def _picked(self, _e=None):
        i = self._sel()
        p = self.st["pictures"][i] if i is not None else None
        self.host.v_bg_name.set(p["name"] if p else "")
        self.c_theme.set(_(dict(THEMES).get(p.get("theme", "light"), "Light")) if p else "")
        self.show_preview()

    def add_pictures(self):
        paths = filedialog.askopenfilenames(title=_("Add pictures"), filetypes=[
            (_("Pictures"), B.PICTURE_TYPES), (_("All files"), "*.*")])
        if not paths:
            return
        pics = self.st["pictures"]
        for path in paths:
            if any(os.path.normcase(p["path"]) == os.path.normcase(path) for p in pics):
                continue
            pics.append({"path": path, "name": B.clean_name(path, [p["name"] for p in pics], max_len=16),
                         "theme": "light"})
        self.refresh_list(select=len(pics) - 1)
        self.host._save_cfg()

    def remove_picture(self):
        i = self._sel()
        if i is None:
            return
        del self.st["pictures"][i]
        self.refresh_list(select=max(0, i - 1))
        self.host._save_cfg()

    def clear_pictures(self):
        if self.st["pictures"] and messagebox.askyesno(APP, _("Remove all pictures from the list?")):
            self.st["pictures"].clear()
            self.refresh_list()
            self.host._save_cfg()

    def _rename(self, _e=None):
        i = self._sel()
        if i is None:
            return
        pics = self.st["pictures"]
        if i >= len(pics):                            # the list on screen is out of date
            return
        typed = self.host.v_bg_name.get()
        if not typed.strip() or typed == pics[i]["name"]:
            self.host.v_bg_name.set(pics[i]["name"])
            return
        pics[i]["name"] = B.clean_name(typed, [p["name"] for j, p in enumerate(pics) if j != i], typed=True)
        self.refresh_list(select=i)
        self.host._save_cfg()

    def choose_logo(self):
        path = filedialog.askopenfilename(title=_("Logo for the PhoneOS phones (PNG with a transparent background "
                                                  "looks best)"),
                                          filetypes=[(_("Pictures"), B.PICTURE_TYPES), (_("All files"), "*.*")])
        if not path:
            return
        self.st["logo"] = os.path.normpath(path)
        self._show_logo()
        self.host._save_cfg()

    def remove_logo(self):
        self.st["logo"] = None
        self._show_logo()
        self.host._save_cfg()

    def _show_logo(self):
        name = os.path.basename(self.st.get("logo") or "")
        self.lbl_logo.configure(text=(name[:15] + "…" if len(name) > 16 else name) or _("none"))
        self.btn_nologo.state(["!disabled"] if name else ["disabled"])

    def rename_all(self):
        """Number every picture from one short name: Wall1, Wall2, ..."""
        pics = self.st["pictures"]
        if not pics:
            return
        base = simpledialog.askstring(APP, _("Short name for all pictures. They are numbered,\n"
                                             "such as Wall1, Wall2 (letters and digits only):"),
                                      initialvalue="Wall", parent=self)
        if base is None or not base.strip():
            return
        base = B.clean_name(base, typed=True, max_len=B.NAME_MAX - 3)
        for n, p in enumerate(pics, 1):
            p["name"] = f"{base}{n}"
        self.refresh_list(select=self._sel())
        self.host._save_cfg()

    def _theme_picked(self, _e=None):
        i = self._sel()
        if i is not None:
            self.st["pictures"][i]["theme"] = next(v for v, t in THEMES if _(t) == self.c_theme.get())

    # ------------------------------------------------------------------ models + preview
    def _models_changed(self):
        keys = checked_models(self.host) or [m[0] for m in B.MODELS]
        labels = [B.BY_KEY[k][2] for k in keys]
        self.c_prev.configure(values=labels)
        if self.host.v_bg_preview.get() not in labels:
            self.host.v_bg_preview.set(labels[0])
        self.show_preview()

    def show_preview(self):
        key = next((m[0] for m in B.MODELS if m[2] == self.host.v_bg_preview.get()), None)
        if key is None:
            return
        m = B.model(key)
        # "x", not "×": a letter keeps "320x212" in this order inside Arabic text
        self.lbl_sizes.configure(text=_("{w}x{h}, thumbnail {tw}x{th}", w=m["full"][0], h=m["full"][1],
                                        tw=m["thumb"][0], th=m["thumb"][1]))
        self.lbl_info.configure(text=m["dir"] + "/")
        self._photos = []
        self.lbl_full.configure(image="", width=PREVIEW[0], height=PREVIEW[1])
        self.lbl_thumb.configure(image="")
        i = self._sel()
        if i is None:
            return
        self.lbl_info.configure(text=m["dir"] + "/" + B.file_names(m, self.st["pictures"][i]["name"])[0])
        try:
            from PIL import Image, ImageTk
            src = B._open(self.st["pictures"][i]["path"])
            full = B.resize(src, m["full"], self.host.v_bg_fit.get())
            if m["colour"] == "grey4":
                full = full.convert("L").point(lambda v: (v // 17) * 17)
            shown = full.copy()
            shown.thumbnail(PREVIEW, Image.LANCZOS)
            thumb = B.resize(src, m["thumb"], self.host.v_bg_fit.get())
            thumb.thumbnail(THUMB_BOX, Image.LANCZOS)    # the 9871 thumbnail is 228x128
            self._photos = [ImageTk.PhotoImage(shown), ImageTk.PhotoImage(thumb)]
            self.lbl_full.configure(image=self._photos[0], width=PREVIEW[0], height=PREVIEW[1])
            self.lbl_thumb.configure(image=self._photos[1])
        except Exception as e:                         # a moved or broken picture file
            self.lbl_info.configure(text=f"{os.path.basename(self.st['pictures'][i]['path'])}: {e}")

    # ------------------------------------------------------------------ status line
    def _message(self, key, **kw):
        self.st["message"] = (key, kw)
        self._show_message()

    def _show_message(self):
        if self.st["message"]:
            key, kw = self.st["message"]
            self.lbl_msg.configure(text=_(key, **kw))

    # ------------------------------------------------------------------ build / save / upload
    def _check(self):
        """Problems the user can fix here, in their language. Returns (pictures, models, fit, logo) or None.
        Read here on the UI thread: Tk variables cannot be read from the worker thread."""
        self._rename()
        pics, keys, logo = list(self.st["pictures"]), checked_models(self.host), self.st.get("logo")
        problem = None
        classic = [B.BY_KEY[k][2] for k in keys if B.model(k)["style"] != "phoneos"]
        if not pics and not logo:
            problem = _("Add at least one picture.")
        elif not keys:
            problem = _("Tick at least one phone model.")
        elif not pics and classic:
            problem = _("{model} phones have no logo: add at least one picture for them.", model=classic[0])
        elif logo and not os.path.isfile(logo):
            problem = _("These pictures are not there any more:") + "\n\n" + logo
        else:
            missing = [p["path"] for p in pics if not os.path.isfile(p["path"])]
            over = [B.BY_KEY[k] for k in keys if len(pics) > B.BY_KEY[k][8]]
            if missing:
                problem = _("These pictures are not there any more:") + "\n\n" + "\n".join(missing[:10])
            elif over:
                problem = _("{model} phones show at most {n} pictures; {have} are in the list.",
                            model=over[0][2], n=over[0][8], have=len(pics))
        if problem:
            messagebox.showwarning(APP, problem)
            return None
        return [dict(p) for p in pics], keys, self.host.v_bg_fit.get(), logo

    def _build_files(self, pics, keys, fit, logo=None):
        self.st["version"] += 1
        version = f"{self.st['version']}.0"
        try:
            return B.build(pics, keys, fit, version=version, log=self.host.log, logo=logo)
        except B.BackgroundError as e:
            raise CLIError(str(e)) from e

    def save_folder(self):
        ok = self._check()
        if not ok:
            return
        root = filedialog.askdirectory(title=_("Folder for the phone background files"), mustexist=True)
        if not root:
            return
        root = os.path.normpath(root)                 # Tk gives C:/Users/...; show it the Windows way

        def run():
            built = self._build_files(*ok)
            n = B.save_folder(built, root)
            self.host.log(f"Saved {n} phone background file(s) under {os.path.join(root, 'Desktops')}")
            self.host.ui(lambda: self._message("Saved {n} files to {path}", n=n, path=os.path.join(root, "Desktops")))
            self.host.ui(os.startfile, os.path.join(root, "Desktops"))
        self.host.task("Save phone backgrounds", run)

    def save_zip(self):
        ok = self._check()
        if not ok:
            return
        path = filedialog.asksaveasfilename(title=_("Save the phone background files"), defaultextension=".zip",
                                            initialfile="phone-backgrounds.zip", filetypes=[("ZIP", "*.zip")])
        if not path:
            return
        path = os.path.normpath(path)

        def run():
            built = self._build_files(*ok)
            try:
                n = B.save_zip(built, path)
            except PermissionError as e:
                raise CLIError(_("Cannot write {path}. Is it open in another program?", path=path)) from e
            self.host.log(f"Saved {n} phone background file(s) to {path}")
            self.host.ui(lambda: self._message("Saved {n} files to {path}", n=n, path=os.path.basename(path)))
        self.host.task("Save phone backgrounds", run)

    def upload(self):
        h = self.host
        ok = self._check()
        if not ok:
            return
        nodes = self.picker.selected()
        try:
            if not nodes:
                raise CLIError(_("Tick at least one TFTP server. Find the nodes with "
                                 "'Connect & discover nodes' on the Cluster tab."))
            user, pw = h.os_creds("cucm")
        except CLIError as e:
            messagebox.showwarning(APP, str(e))
            return
        pics, keys, fit, logo = ok
        folders = [B.model(k)["dir"] for k in keys]
        restart, keep = bool(h.v_bg_restart.get()), bool(h.v_bg_keep.get())
        # Cisco TFTP is a feature service: only the Serviceability API restarts it, with an application user
        axl = (h.v_axluser.get().strip(), h.v_axlpw.get())
        if restart and not all(axl):
            messagebox.showwarning(APP, _("Restarting Cisco TFTP needs the AXL user and password on the Cluster tab "
                                          "(CUCM restarts it through its Serviceability API, not the OS admin "
                                          "login). Enter them, or untick 'Restart Cisco TFTP after the upload'."))
            return
        with_logo = logo and any(B.model(k)["style"] == "phoneos" for k in keys)
        if not messagebox.askyesno(APP, _("Upload {n} pictures to these folders:", n=len(pics)) + "\n"
                                   + "\n".join("  • " + d for d in folders)
                                   + ("\n" + _("and the logo to the PhoneOS folders") if with_logo else "")
                                   + "\n\n" + _("on:") + "\n"
                                   + "\n".join(f"  • {n.get('hostname', '')} ({n['host']})" for n in nodes) + "\n\n"
                                   + (_("Pictures each List.xml already lists stay; these are added after them.")
                                      if keep else _("A List.xml already in these folders is replaced."))
                                   + ("\n" + _("Cisco TFTP restarts on each node afterwards.") if restart else "")):
            return
        h.task("Upload phone backgrounds", self._upload_run, pics, keys, fit, nodes, user, pw, restart, keep, logo,
               axl)

    def _merged(self, host, built, keep):
        """This node's copy of the files: each List.xml merged with the one its TFTP server has now."""
        if not keep:
            return built
        out = {}
        for d, files in built.items():
            m = next(B.model(k) for k in B.BY_KEY if B.model(k)["dir"] == d)
            now = B.fetch(host, d, "List.xml")
            if now is None:
                out[d] = files
                continue
            try:
                merged, kept = B.merge_list(m, now, files[-1][1])
            except B.BackgroundError as e:
                raise B.BackgroundError(f"{host}: {d}: {e}. Untick 'Keep what List.xml on the server lists' "
                                        "to replace it.") from e
            self.host.log(f"[{host}] {d}/List.xml: kept {kept} entr{'y' if kept == 1 else 'ies'} already listed there")
            out[d] = files[:-1] + [("List.xml", merged)]
        return out

    def _upload_run(self, pics, keys, fit, nodes, user, pw, restart, keep=False, logo=None, axl=("", "")):
        h, picker = self.host, self.picker
        common = self._build_files(pics, keys, fit, logo)
        good = restart_failed = 0
        for n in nodes:
            host = n["host"]
            if h.cancel.is_set():
                break
            try:
                picker.set_status(host, _("reading the List.xml files on the server…") if keep else _("signing in…"),
                                  "run")
                built = self._merged(host, common, keep)
                lists = [(d, files[-1][1]) for d, files in built.items()]      # List.xml is last in each folder
                picker.set_status(host, _("signing in…"), "run")

                def prog(done, total, host=host):
                    picker.set_status(host, _("uploading {done}/{total}…", done=done, total=total), "run")
                B.TftpUploader(host, user, pw).upload_all(built, log=h.log, cancel=h.cancel, progress=prog)
            except (B.BackgroundError, CLIError) as e:
                picker.set_status(host, "✗ " + str(e).splitlines()[0][:150], "bad")
                h.log(f"[{host}] phone backgrounds: {e}")
                continue
            good += 1
            restarted = not restart
            if restart:                                   # the files are on the node now, whatever happens here
                try:
                    picker.set_status(host, _("restarting Cisco TFTP…"), "run")
                    B.restart_tftp(host, axl[0], axl[1], node_names=[n.get("hostname", ""), host],
                                   cancel=h.cancel, log=h.log)
                    restarted = True
                except B.TftpNotActive as e:
                    picker.set_status(host, "✓ " + _("uploaded; Cisco TFTP is not activated on this node"), "run")
                    h.log(f"[{host}] files uploaded. {e} - phones do not get files from this node")
                    continue
                except (B.BackgroundError, CLIError) as e:
                    restart_failed += 1
                    picker.set_status(host, "✗ " + _("uploaded, but Cisco TFTP did not restart"), "bad")
                    h.log(f"[{host}] files uploaded, but {e}")
                    if getattr(e, "output", ""):
                        h.log(f"[{host}] CUCM replied:\n" + "\n".join("    " + ln for ln in e.output.strip().splitlines()))
                    continue
            try:
                picker.set_status(host, _("checking the phones can fetch List.xml…"), "run")
                secs = 120 if restarted and restart else 0
                served = all(B.wait_served(host, d, "List.xml", data, secs=secs, cancel=h.cancel) for d, data in lists)
            except (B.BackgroundError, CLIError):
                served = False
            if served:
                picker.set_status(host, "✓ " + _("uploaded; phones get the new pictures"), "ok")
                h.log(f"[{host}] phone backgrounds uploaded; TFTP serves the new List.xml")
            else:
                picker.set_status(host, "✓ " + _("uploaded; TFTP still serves the old List.xml - restart Cisco TFTP"),
                                  "run")
                h.log(f"[{host}] phone backgrounds uploaded, but TFTP (port 6970) does not serve the new List.xml yet")
        h.log(f"Phone backgrounds: uploaded to {good}/{len(nodes)} TFTP server(s)"
              + (f", Cisco TFTP restart failed on {restart_failed}" if restart_failed else ""))
        h.ui(lambda: self._message("Uploaded to {good} of {n} TFTP servers", good=good, n=len(nodes)))
        if good < len(nodes) and not h.cancel.is_set():
            raise CLIError(_("Upload failed on {n} TFTP server(s). See the TFTP servers list and the activity log.",
                             n=len(nodes) - good))
        if restart_failed:
            raise CLIError(_("The files are uploaded, but Cisco TFTP did not restart on {n} node(s), so phones keep the "
                             "old list. CUCM's reply is in the activity log. Restart Cisco TFTP in Cisco Unified "
                             "Serviceability › Tools › Control Center - Feature Services.", n=restart_failed))
