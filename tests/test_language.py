"""Language switch at runtime: English -> Arabic -> English keeps what was typed, the log,
the Backup cluster choice and a running SFTP server. Uses a temp config - never the real one."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import i18n
import maint_app

_tmp = tempfile.mkdtemp()
maint_app.CONFIG = os.path.join(_tmp, "config.json")
maint_app.LOG_DIR = os.path.join(_tmp, "logs")
maint_app.REPORT_DIR = os.path.join(_tmp, "reports")
json.dump({"language": "en"}, open(maint_app.CONFIG, "w"))

app = maint_app.App()
app.update()
app.v_pub.set("10.9.9.9")
app.v_ospw.set("typed-not-saved")          # Remember passwords is off: must survive the rebuild anyway
app.v_root.set(os.path.join(_tmp, "root"))
app.v_port.set("2041")
app.v_ip.set("127.0.0.1")
app.v_bkcl.set("cuc")
app._bk_switch()
app.start_sftp()
app.log("before switch")
app.update()
assert app.server.running

app.lang_cb.set(i18n.LANGUAGES["ar"])
app._language_picked()
app.update()
assert i18n.language() == "ar" and app.rtl
assert app.v_pub.get() == "10.9.9.9" and app.v_ospw.get() == "typed-not-saved"
assert app._bk_cur == "cuc" and app.v_feat.get() == "CUC" and app.v_bkdir.get() == "/backup_cuc"
assert app.server.running and app.sftp_stop_btn.instate(["!disabled"])
assert "before switch" in app.logbox.get("1.0", "end")
assert app.nb.tab(app.nb.tabs()[-1], "text").strip("‫‬‏") == "المجموعة"   # first tab on the right
assert json.load(open(maint_app.CONFIG, encoding="utf-8"))["language"] == "ar"
assert "os_password" not in json.load(open(maint_app.CONFIG, encoding="utf-8"))

app.lang_cb.set(i18n.LANGUAGES["en"])
app._language_picked()
app.update()
assert not app.rtl and app.nb.tab(app.nb.tabs()[0], "text") == "Cluster"
assert app.v_pub.get() == "10.9.9.9" and app._bk_cur == "cuc" and app.server.running

app.stop_sftp()
app.destroy()
print("LANGUAGE OK")
