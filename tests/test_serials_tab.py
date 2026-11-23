"""Phone Serials tab wiring: target counting, CUCM discovery with the Cluster tab's AXL login and the
tab's node box, a scan that keeps running through a language switch, Arabic text, filter, settings
(no phone password) and Excel export. Phones and CUCM are faked. Uses a temp config, never the real one."""
import json
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import grabber_engine as E
import i18n
import maint_app
import serials_panel

_tmp = tempfile.mkdtemp()
maint_app.CONFIG = os.path.join(_tmp, "config.json")
maint_app.LOG_DIR = os.path.join(_tmp, "logs")
maint_app.REPORT_DIR = os.path.join(_tmp, "reports")
json.dump({"language": "en"}, open(maint_app.CONFIG, "w"))
said = []
mb = serials_panel.messagebox
mb.showwarning = mb.showerror = mb.showinfo = lambda *a, **k: said.append(a[1])
mb.askyesno = lambda *a, **k: (said.append(a[1]), False)[1]       # skips "open the file now?"

gate = threading.Event()
gate.set()
scanned, discovered = [], {}


def fake_scan(targets, workers, timeout, try_https, auth, stop_event, extra, on_result):
    scanned.append((list(targets), workers, timeout, try_https, auth))
    for n, ip in enumerate(targets, 1):
        gate.wait(10)
        last = ip.split(".")[-1]
        r = {"ip": ip, "status": E.ST_DOWN, "note": "TCP 80/443 closed or host down"}
        if last in ("1", "2"):
            r = {"ip": ip, "status": E.ST_OK, "model": "CP-8845", "serial": f"FCH00SER{last}",
                 "mac": f"00AABBCCDD0{last}", "source": "http XML"}
        r.update({k: v for k, v in extra.get(ip, {}).items() if v and not r.get(k)})
        on_result(r, n, len(targets))


def fake_discover(host, user, pw, status, log):
    discovered.update(host=host, user=user, pw=pw, status=status)
    log("RisPort wildcard page 1: 3 entries")
    return [{"name": "SEP00AABBCCDD01", "ip": "10.5.0.1", "dn": "2001", "desc": "Lobby", "status": "Registered",
             "httpd": "Yes"},
            {"name": "SEP00AABBCCDD09", "ip": "10.5.0.9", "dn": "2009", "desc": "Store", "status": "Registered",
             "httpd": "No"},
            {"name": "SEP00AABBCCDD07", "ip": "", "dn": "2007", "desc": "", "status": "UnRegistered", "httpd": ""}]


serials_panel.E.scan = fake_scan
serials_panel.E.cucm_discover = fake_discover

app = maint_app.App()
app.update()
P = lambda: app.serials_panel                                    # noqa: E731 - the panel is rebuilt on a switch
tab_texts = lambda: [app.nb.tab(t, "text").strip("‫‬‏") for t in app.nb.tabs()]   # noqa: E731


def settle(cond, secs=10):
    end = time.time() + secs
    while time.time() < end:
        app.update()
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("timed out")


def rows():
    return [P().tv.item(i, "values") for i in P().tv.get_children()]


assert tab_texts()[4:6] == ["MACD", "Phone Serials"], tab_texts()

# ---- every text on the tab has Arabic: string keys given to _() or _message(), plus headings and statuses
import ast
src = open(serials_panel.__file__, encoding="utf-8").read()
keys = set()
for node in ast.walk(ast.parse(src)):
    if isinstance(node, ast.Call) and (getattr(node.func, "id", "") == "_" or getattr(node.func, "attr", "") in
                                       ("_message",)) and node.args and isinstance(node.args[0], ast.Constant):
        keys.add(node.args[0].value)
    if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "_message" and node.args and \
            isinstance(node.args[0], ast.IfExp):
        keys.update({node.args[0].body.value, node.args[0].orelse.value})
    if isinstance(node, ast.Tuple) and len(node.elts) == 2 and all(isinstance(e, ast.Constant) for e in node.elts) \
            and isinstance(node.elts[0].value, str) and node.elts[0].value[:1].isupper():
        keys.update(e.value for e in node.elts if isinstance(e.value, str) and " " in e.value or e.value in
                    ("Export Excel", "Export CSV"))
keys |= {head for _k, head, _w in E.COLUMNS} | {E.ST_OK, E.ST_PARTIAL, E.ST_NOWEB, E.ST_NOTPHONE, E.ST_DOWN,
                                                 E.ST_ERROR}
keys -= {"Excel", "CSV"}
missing = sorted(k for k in keys if k not in i18n.AR)
assert len(keys) > 70 and not missing, missing

# ---- targets are counted, bad entries flagged
P().t_targets.insert("1.0", "10.0.0.1-3\nnot_an_ip!\n")
P()._targets_changed()
P()._count_targets()
assert P().lbl_count.cget("text") == "3 addresses  ·  1 invalid", P().lbl_count.cget("text")

# ---- invalid entries: the user is asked first, "No" scans nothing
P().start()
assert "not valid" in said[-1] and not scanned

# ---- a scan; settings come from the tab
P().t_targets.delete("1.0", "end")
P().t_targets.insert("1.0", "10.0.0.1-3")
P()._targets_changed()
app.v_ser_workers.set("32")
app.v_ser_timeout.set("2.5")
app.v_ser_https.set(False)
app.v_ser_puser.set("webadmin")
app.v_ser_ppw.set("webpw99")
P().start()
settle(lambda: not app.serials_state["running"])
assert scanned[-1] == (["10.0.0.1", "10.0.0.2", "10.0.0.3"], 32, 2.5, False, ("webadmin", "webpw99")), scanned[-1]
assert [r[0] for r in rows()] == ["10.0.0.1", "10.0.0.2", "10.0.0.3"], rows()
assert rows()[0][3] == "FCH00SER1" and rows()[2][1] == "No response"
assert P().lbl_stats.cget("text") == "2 serials   ·   1 models   ·   No response: 1", P().lbl_stats.cget("text")
assert "Finished" in P().lbl_prog.cget("text") and "2 serial numbers" in P().lbl_prog.cget("text")
assert "Phone serials: finished, 2 serial numbers read" in app.logbox.get("1.0", "end")

# ---- filter and "phones only"
app.v_ser_filter.set("ser2")
assert [r[0] for r in rows()] == ["10.0.0.2"], rows()
app.v_ser_filter.set("")
app.v_ser_only_ok.set(True)
P().refresh_tree()
assert len(rows()) == 2
app.v_ser_only_ok.set(False)
P().refresh_tree()

# ---- CUCM discovery: needs the Cluster tab's AXL login, uses the node picked on this tab
app.v_axluser.set("")
P().discover()
assert "AXL" in said[-1] and not discovered
app.nodes = [{"host": "10.0.0.20", "hostname": "sub1", "role": "Subscriber", "type": "CUCM", "cluster": "cucm"},
             {"host": "10.0.0.10", "hostname": "pub", "role": "Publisher", "type": "CUCM", "cluster": "cucm"}]
app.v_ser_node.set("")
app._nodes_changed()
assert app.v_ser_node.get().startswith("10.0.0.10 ") and len(P().c_node["values"]) == 2
app.v_ser_node.set(P().c_node["values"][1])
app.v_axluser.set("axladmin")
app.v_axlpw.set("axlpw")
P().c_status.set("All phones")
P()._status_picked()
P().discover()
settle(lambda: not app.serials_state["discovering"])
assert discovered == {"host": "10.0.0.20", "user": "axladmin", "pw": "axlpw", "status": "Any"}, discovered
assert "3 phones; 2 IP addresses" in said[-1] and "1 had no IP" in said[-1] and "1 have their web server" in said[-1]
assert P().t_targets.get("1.0", "end").split() == ["10.0.0.1-3", "10.5.0.1", "10.5.0.9"]
assert app.serials_state["extra"]["10.5.0.9"]["hostname"] == "SEP00AABBCCDD09"

# ---- a scan keeps running through a switch to Arabic, and lands in the rebuilt tab
gate.clear()
P().start(["10.5.0.1", "10.5.0.9"])
settle(lambda: app.serials_state["running"])
assert P().btn_start.instate(["disabled"]) and not P().btn_stop.instate(["disabled"])
app.lang_cb.set(i18n.LANGUAGES["ar"])
app.log("queued just before a language switch")
app._language_picked()
app.update()
assert i18n.language() == "ar" and P().btn_start.instate(["disabled"]), "rebuilt tab still shows the scan"
assert "queued just before a language switch" in app.logbox.get("1.0", "end"), "log line lost in the switch"
gate.set()
settle(lambda: not app.serials_state["running"])
assert len(app.serials_state["results"]) == 5
lobby = next(r for r in rows() if r[0] == "10.5.0.1")
assert lobby[5] == "SEP00AABBCCDD01" and lobby[6] == "2001", lobby           # CUCM fields merged in
assert lobby[1].strip("‫‬‏") == "ناجح", lobby[1]
assert "Phone Serials" not in tab_texts() and "أرقام تسلسل الهواتف" in tab_texts(), tab_texts()
assert P().tv.heading("serial", "text").strip("‫‬‏") == "الرقم التسلسلي"
assert list(P().tv["displaycolumns"])[0] == "note", "columns read right to left"
assert P().t_targets.get("1.0", "end").split() == ["10.0.0.1-3", "10.5.0.1", "10.5.0.9"], "targets kept"
assert app.v_ser_workers.get() == "32" and app.v_ser_puser.get() == "webadmin", "settings kept"
assert P().c_status.get().strip("‫‬‏") == "كل الهواتف"

# ---- settings saved; the phone web password is not
app._save_cfg()
raw = open(maint_app.CONFIG, encoding="utf-8").read()
saved = json.loads(raw)["serials"]
assert saved["node"].startswith("10.0.0.20 ") and saved["status"] == "Any" and saved["workers"] == 32
assert saved["timeout"] == 2.5 and saved["https"] is False and saved["phone_user"] == "webadmin"
assert "10.5.0.9" in saved["targets"] and "webpw99" not in raw

# ---- Excel export, statuses in English
out = os.path.join(_tmp, "phones.xlsx")
serials_panel.filedialog.asksaveasfilename = lambda **k: out
P().export("xlsx")
from openpyxl import load_workbook
ws = load_workbook(out)["Phones"]
found = {ws.cell(r, 1).value: (ws.cell(r, 2).value, ws.cell(r, 4).value) for r in range(5, ws.max_row + 1)}
assert found["10.0.0.2"] == ("OK", "FCH00SER2") and found["10.5.0.9"][0] == "No response", found
assert len(found) == 5

app.lang_cb.set(i18n.LANGUAGES["en"])
app._language_picked()
app.update()
assert len(rows()) == 5 and "Phone Serials" in tab_texts()
app.destroy()
print("SERIALS TAB OK")
