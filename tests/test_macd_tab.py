"""MACD tab wiring: connects with the Cluster tab's publisher + AXL login, fills the
drop-downs, keeps the connection across a language switch, and refuses to connect
without a login. AXL itself is faked here. Uses a temp config - never the real one."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import i18n
import macd_panel
import maint_app

_tmp = tempfile.mkdtemp()
maint_app.CONFIG = os.path.join(_tmp, "config.json")
maint_app.LOG_DIR = os.path.join(_tmp, "logs")
maint_app.REPORT_DIR = os.path.join(_tmp, "reports")
json.dump({"language": "en"}, open(maint_app.CONFIG, "w"))
warnings = []
macd_panel.messagebox.showwarning = lambda *a, **k: warnings.append(a[1])
macd_panel.messagebox.showerror = lambda *a, **k: warnings.append(a[1])
used = {}


class FakeAXL:
    def __init__(self, host, user, pw, version, port, verify):
        used.update(host=host, user=user, pw=pw, version=version, port=port)
        self.host, self.version = host, version

    def get_version(self):
        return "14.0.1.13900-155"

    def detect_version(self):
        return "14.0", "14.0.1.13900-155"


class FakeMACD:
    def __init__(self, client, log=None, operator=""):
        self.client = client

    def dropdowns(self):
        return {"devicePools": ["DP_HQ", "DP_BR"], "partitions": ["PT_Internal"]}


macd_panel.AXLClient = FakeAXL
macd_panel.MACD = FakeMACD

app = maint_app.App()
app.update()


def wait():
    for _ in range(100):
        app.update()
        if not app.busy:
            return
        app.after(50)
        app.update_idletasks()
        import time
        time.sleep(0.05)


# no login -> warning, no connection
app.macd_panel.connect()
assert warnings and "AXL" in warnings[-1] and not app.macd_state

app.v_pub.set("10.9.9.9")
app.v_axluser.set("axladmin")
app.v_axlpw.set("axlpw")
app.macd_panel.connect(detect=True)
wait()
assert used == {"host": "10.9.9.9", "user": "axladmin", "pw": "axlpw", "version": "14.0", "port": 8443}, used
assert app.macd_state["conn_info"][0] == "10.9.9.9" and app.macd_panel.lists["devicePools"] == ["DP_HQ", "DP_BR"]
assert "Connected: 10.9.9.9" in app.macd_panel.c_info.cget("text")
assert "Connected to 10.9.9.9" in app.logbox.get("1.0", "end")

app.lang_cb.set(i18n.LANGUAGES["ar"])
app._language_picked()
app.update()
assert app.macd_panel.macd is not None and app.macd_panel.lists["partitions"] == ["PT_Internal"]
dp_boxes = app.macd_panel.combos.get("devicePools", [])
assert dp_boxes and list(dp_boxes[0]["values"]) == ["DP_HQ", "DP_BR"], "drop-downs refilled after rebuild"
assert app.nb.tab(app.nb.tabs()[2], "text").strip("‫‬‏") == "MACD"
assert json.load(open(maint_app.CONFIG, encoding="utf-8"))["macd"]["version"] == "14.0"

app.lang_cb.set(i18n.LANGUAGES["en"])
app._language_picked()
app.update()

# node choice: publisher by default, IM&P left out, a subscriber or a typed address can be picked
app.nodes = [{"host": "10.0.0.2", "hostname": "sub1", "role": "Subscriber", "type": "CUCM", "cluster": "cucm"},
             {"host": "10.0.0.1", "hostname": "pub", "role": "Publisher", "type": "CUCM", "cluster": "cucm"},
             {"host": "10.0.0.3", "hostname": "imp", "role": "Publisher", "type": "IM&P", "cluster": "cucm"},
             {"host": "10.0.1.1", "hostname": "cucpub", "role": "Publisher", "type": "Unity", "cluster": "cuc"}]
app.v_macd_node.set("")
app.v_inv_node.set("")
app._nodes_changed()
assert app.v_macd_node.get().startswith("10.0.0.1 "), app.v_macd_node.get()
values = list(app.macd_panel.c_node["values"])
assert len(values) == 2 and values[0].startswith("10.0.0.1 ") and values[1].startswith("10.0.0.2 "), values
assert app.v_inv_node.get().startswith("10.0.0.1 ")

app.v_macd_node.set(values[1])
app.macd_panel.connect()
wait()
assert used["host"] == "10.0.0.2", used
assert "subscriber" in app.macd_panel.c_info.cget("text")
app.v_macd_node.set("cucm-typed.lab")
app.macd_panel.connect()
wait()
assert used["host"] == "cucm-typed.lab", used
assert "subscriber" not in app.macd_panel.c_info.cget("text")

# inventory: the node box follows the source; the export goes to the node picked
app.v_invsrc.set("cuc")
app._inv_source_picked()
assert app.v_inv_node.get().startswith("10.0.1.1 ") and len(app.inv_node_cb["values"]) == 1
assert "Users" in app.sql_list.get(0, "end") and "Phones" not in app.sql_list.get(0, "end")
app.lang_cb.set(i18n.LANGUAGES["ar"])
app._language_picked()
app.update()
assert "Phones" not in app.sql_list.get(0, "end"), "list follows the source after a language switch"
assert app.v_inv_node.get().startswith("10.0.1.1 ")
app.lang_cb.set(i18n.LANGUAGES["en"])
app._language_picked()
app.update()
app.v_invsrc.set("cucm")
app._inv_source_picked()
values = list(app.inv_node_cb["values"])
app.v_inv_node.set(values[1])
targets = []


class FakeSQL:
    version = "14.0"

    def __init__(self, host, user, pw):
        targets.append((host, user, pw))


maint_app.ops.AXLSQL = FakeSQL
maint_app.ops.export_sql_to_excel = lambda *a, **k: None
maint_app.os.startfile = lambda p: None
maint_app.filedialog.asksaveasfilename = lambda **k: os.path.join(_tmp, "inv.xlsx")
app._sql_export()
wait()
assert targets == [("10.0.0.2", "axladmin", "axlpw")], targets

saved = app.v_inv_node.get()
app._save_cfg()
assert json.load(open(maint_app.CONFIG, encoding="utf-8"))["inv_node"] == saved
app.v_invsrc.set("cuc")
app._inv_source_picked()
app._save_cfg()
assert json.load(open(maint_app.CONFIG, encoding="utf-8"))["inv_node"] == saved, "CUC pick not saved as CUCM node"
app.destroy()
print("MACD TAB OK")
