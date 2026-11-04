"""Phones + DNs export: the query's join logic (on a small SQLite copy of the CUCM tables),
the single-sheet Excel file, and the button (AXL faked). Uses a temp config - never the real one."""
import json
import os
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from openpyxl import load_workbook

import cucm_ops as ops
import i18n
import maint_app

# ---- join logic
db = sqlite3.connect(":memory:")
db.row_factory = sqlite3.Row
db.executescript("""
CREATE TABLE typeclass(enum, name); CREATE TABLE typemodel(enum, name); CREATE TABLE typedeviceprotocol(enum, name);
CREATE TABLE devicepool(pkid, name); CREATE TABLE callingsearchspace(pkid, name); CREATE TABLE enduser(pkid, userid);
CREATE TABLE routepartition(pkid, name);
CREATE TABLE device(pkid, name, description, tkclass, tkmodel, tkdeviceprotocol, fkdevicepool, fkcallingsearchspace, fkenduser);
CREATE TABLE numplan(pkid, dnorpattern, description, alertingname, fkroutepartition, fkcallingsearchspace_sharedlineappear);
CREATE TABLE devicenumplanmap(fkdevice, fknumplan, numplanindex, display, label, e164mask);
INSERT INTO typeclass VALUES (1,'Phone'),(2,'Gateway');
INSERT INTO typemodel VALUES (1,'Cisco 8845'); INSERT INTO typedeviceprotocol VALUES (1,'SIP');
INSERT INTO devicepool VALUES ('dp','DP_HQ'); INSERT INTO callingsearchspace VALUES ('c1','CSS_Dev'),('c2','CSS_Line');
INSERT INTO enduser VALUES ('u1','asha'); INSERT INTO routepartition VALUES ('p1','PT_Int');
INSERT INTO device VALUES
 ('d1','SEPAAA','Two lines',1,1,1,'dp','c1','u1'),
 ('d2','SEPBBB','Shares 5001',1,1,1,'dp',NULL,NULL),
 ('d3','SEPCCC','No line',1,1,1,'dp',NULL,NULL),
 ('g1','GW1','A gateway',2,1,1,'dp',NULL,NULL);
INSERT INTO numplan VALUES ('n1','5001','Reception','Reception','p1','c2'),('n2','5002','Asha','Asha','p1',NULL),('n3','5003',NULL,NULL,NULL,NULL);
INSERT INTO devicenumplanmap VALUES
 ('d1','n1',1,'Rec','Rec','+96812345001'),('d1','n2',2,'Asha','Asha',NULL),('d2','n1',1,'Rec','Rec',NULL),('g1','n3',1,NULL,NULL,NULL);
""")
rows = [dict(r) for r in db.execute(ops.PHONES_WITH_DNS_SQL)]
got = [(r["device"], r["line"], r["dn"]) for r in rows]
assert got == [("SEPAAA", 1, "5001"), ("SEPAAA", 2, "5002"), ("SEPBBB", 1, "5001"), ("SEPCCC", None, None)], got
first = rows[0]
assert (first["model"], first["device_pool"], first["device_css"], first["owner_user"]) == ("Cisco 8845", "DP_HQ", "CSS_Dev", "asha")
assert (first["partition"], first["line_css"], first["external_mask"]) == ("PT_Int", "CSS_Line", "+96812345001")

# ---- the button, through to a real file
_tmp = tempfile.mkdtemp()
maint_app.CONFIG = os.path.join(_tmp, "config.json")
maint_app.LOG_DIR = os.path.join(_tmp, "logs")
maint_app.REPORT_DIR = os.path.join(_tmp, "reports")
json.dump({"language": "en", "sftp_root": os.path.join(_tmp, "root")}, open(maint_app.CONFIG, "w"))
out = os.path.join(_tmp, "phones.xlsx")
errors, targets = [], []
maint_app.messagebox.showerror = lambda *a, **k: errors.append(a[1])
maint_app.messagebox.showwarning = lambda *a, **k: errors.append(a[1])
maint_app.filedialog.asksaveasfilename = lambda **k: out
maint_app.os.startfile = lambda p: None


class FakeSQL:
    version = "12.5"

    def __init__(self, host, user, pw):
        targets.append(host)

    def query(self, sql):
        assert sql == ops.PHONES_WITH_DNS_SQL
        return [{k: "" if v is None else str(v) for k, v in r.items()} for r in rows]


maint_app.ops.AXLSQL = FakeSQL
app = maint_app.App()
app.update()


def wait():
    for _ in range(200):
        app.update()
        if not app.busy:
            return
        time.sleep(0.05)
    raise AssertionError("still busy")


app._phones_dns_export()                      # no AXL login: warning, nothing written
assert errors and not os.path.exists(out)
errors.clear()
app.v_axluser.set("axladmin")
app.v_axlpw.set("axlpw")
app.v_inv_node.set("10.0.0.2  (sub1, Subscriber)")
app.after(0, app._phones_dns_export)


def check():
    if app.busy or not os.path.exists(out):
        app.after(100, check)
    else:
        app.after(300, app.quit)


app.after(300, check)
app.after(30000, app.quit)
app.mainloop()
assert not errors, errors
assert targets == ["10.0.0.2"], targets
wb = load_workbook(out)
assert wb.sheetnames == ["Phones and DNs"], wb.sheetnames
ws = wb.active
assert ws.max_row == 5 and ws.cell(1, 1).value == "device" and ws.cell(1, 9).value == "dn"
assert ws.cell(2, 1).value == "SEPAAA" and ws.cell(2, 9).value == "5001"

# not offered for Unity Connection
app.v_invsrc.set("cuc")
app._inv_source_picked()
assert app.combo_btn.instate(["disabled"])
app.lang_cb.set(i18n.LANGUAGES["ar"])
app._language_picked()
app.update()
assert app.combo_btn.instate(["disabled"]), "stays disabled after a language switch"
app.destroy()
print("PHONE DN EXPORT OK")
