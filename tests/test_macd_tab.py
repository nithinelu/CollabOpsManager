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
app.destroy()
print("MACD TAB OK")
