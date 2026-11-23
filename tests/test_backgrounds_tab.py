"""Phone Backgrounds tab: pictures resized per model, List.xml per folder, save to ZIP / folder, and upload
to the TFTP nodes through a fake OS Administration upload page (login + Struts token), TFTP restart over a
fake CLI, Arabic text, a language switch and the saved settings. Uses a temp config, never the real one."""
import io
import json
import os
import re
import sys
import tempfile
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image

import backgrounds_panel as BP
import i18n
import maint_app
import phone_backgrounds as B

_tmp = tempfile.mkdtemp()
maint_app.CONFIG = os.path.join(_tmp, "config.json")
maint_app.LOG_DIR = os.path.join(_tmp, "logs")
maint_app.REPORT_DIR = os.path.join(_tmp, "reports")
json.dump({"language": "en"}, open(maint_app.CONFIG, "w"))
said, answers = [], []
for mb in (BP.messagebox, maint_app.messagebox):
    mb.showwarning = mb.showerror = mb.showinfo = lambda *a, **k: said.append(a[1])
    mb.askyesno = lambda *a, **k: (said.append(a[1]), answers.pop(0) if answers else False)[1]
BP.os.startfile = lambda p: None

# ---- pictures on disk
pics_dir = os.path.join(_tmp, "pics")
os.makedirs(pics_dir)
paths = []
for name, size, colour in (("Company Logo.jpg", (1920, 1080), (200, 30, 30)), ("beach!.png", (600, 900), (0, 90, 200)),
                           ("Company-Logo.png", (300, 300), (10, 200, 10))):
    p = os.path.join(pics_dir, name)
    Image.new("RGB", size, colour).save(p)
    paths.append(p)


# ---- fake CUCM: OS Administration upload page per node, TFTP restart, TFTP HTTP (6970)
class Resp:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status


class FakeCucm:
    def __init__(self):
        self.files, self.restarts, self.logins, self.serving = {}, [], [], {}
        self.password = "Platform#1"


cucm = {}


def node_of(host):
    return cucm.setdefault(host, FakeCucm())


class FakeSession:
    verify = True

    def __init__(self, host):
        self.node, self.logged_in, self.token, self.n = node_of(host), False, None, 0

    def _form(self):
        self.n += 1
        self.token = f"TOK{self.n}"
        return (f'<form action="tftpFileUpload.do" method="post" enctype="multipart/form-data">'
                f'<input type="hidden" name="struts.token.name" value="token">'
                f'<input type="hidden" name="token" value="{self.token}"><input type="file" name="file"></form>')

    def get(self, url, timeout=None):
        if url.endswith("/tftpFileUpload.do"):
            return Resp(self._form() if self.logged_in else
                        '<form action="j_security_check"><input name="j_password"></form>')
        return Resp("<html>login</html>")

    def post(self, url, timeout=None, data=None, files=None):
        if url.endswith("/j_security_check"):
            self.node.logins.append(data["j_username"])
            self.logged_in = data == {"appNav": "cmplatform", "j_username": "osadmin", "j_password": self.node.password}
            return Resp("ok")
        assert url.endswith("/tftpFileUpload.do") and self.logged_in
        if files["token"][1] != self.token or files["struts.token.name"][1] != "token":
            return Resp('<span class="errorText">You have pressed Submit twice</span>' + self._form())
        name, data_, _ct = files["file"]
        self.node.files[(files["directory"][1], name)] = data_
        return Resp('<p class="content">File uploaded successfully</p>' + self._form())


class FakeUploader(B.TftpUploader):
    def __init__(self, host, user, password, timeout=60, session=None):
        super().__init__(host, user, password, timeout, session=FakeSession(host))


BP.B.TftpUploader = FakeUploader


class HttpResp:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status


def _svc_reply(op, status, reason=""):
    return (f'<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body>'
            f'<ns1:{op}Response xmlns:ns1="http://schemas.cisco.com/ast/soap"><ns1:ServiceInfoList><ns1:item>'
            f'<ns1:ServiceName>Cisco Tftp</ns1:ServiceName><ns1:ServiceStatus>{status}</ns1:ServiceStatus>'
            f'<ns1:ReasonCode>-1</ns1:ReasonCode><ns1:ReasonCodeString>{reason}</ns1:ReasonCodeString>'
            f'<ns1:StartTime>Mon Nov 23 13:30:00 2026</ns1:StartTime></ns1:item></ns1:ServiceInfoList>'
            f'</ns1:{op}Response></soapenv:Body></soapenv:Envelope>')


def fake_control_center(url, data=None, headers=None, auth=None, verify=True, timeout=None):
    """CUCM's Serviceability Control Center API (feature services), one node per URL."""
    host = re.match(r"https://([^:/]+):8443/controlcenterservice2/services/ControlCenterServices$", url).group(1)
    node, body = node_of(host), data.decode()
    if auth != ("axluser", "AxlPw#1"):
        return HttpResp("Unauthorized", 401)
    fault = lambda text: HttpResp("<soapenv:Envelope><soapenv:Body><soapenv:Fault><faultcode>soapenv:Server</faultcode>"
                                  f"<faultstring>{text}</faultstring></soapenv:Fault></soapenv:Body></soapenv:Envelope>",
                                  500)                                                      # noqa: E731
    if "soapDoControlServices" in body:
        assert headers["SOAPAction"] == '"soapDoControlServices"' and "<soap:item>Cisco Tftp</soap:item>" in body
        m = re.search(r"<soap:ControlServiceRequest><soap:NodeName>([^<]*)</soap:NodeName>"
                      r"<soap:ControlType>Restart</soap:ControlType><soap:ServiceList>", body)
        if not m:                                                  # CUCM 12.5's Axis2 checks the element order
            return fault("org.apache.axis2.databinding.ADBException: Unexpected subelement ControlType")
        if m.group(1) != getattr(node, "server_name", {"10.9.0.1": "pub", "10.9.0.2": "sub"}.get(host, host)):
            return fault(f"Node {m.group(1)} is not a server of this cluster")
        node.restarts.append("restart Cisco Tftp")
        if getattr(node, "restart_fault", None):
            return HttpResp(f"<soapenv:Fault><faultstring>{node.restart_fault}</faultstring></soapenv:Fault>", 500)
        if getattr(node, "tftp_state", "") == "not active":
            return HttpResp(_svc_reply("soapDoControlServices", "Stopped", "Service Not Activated"))
        node.serving = {k: v for k, v in node.files.items()}       # TFTP now hands out what is on disk
        node.polls = 0
        return HttpResp(_svc_reply("soapDoControlServices", "Starting"))
    assert headers["SOAPAction"] == '"soapGetServiceStatus"' and "soapGetServiceStatus" in body
    if getattr(node, "status_needs_empty", False) and "<soap:item>" in body:
        return fault("org.apache.axis2.databinding.ADBException: Unexpected subelement item")
    node.polls += 1
    return HttpResp(_svc_reply("soapGetServiceStatus", "Started"))


BP.B._http_post = fake_control_center
_real_restart = B.restart_tftp
BP.B.restart_tftp = lambda *a, **k: _real_restart(*a, **{**k, "poll": 0.05})    # no 5 s waits in the test


def fake_served(host, directory, name, data, timeout=8, http_get=None):
    return node_of(host).serving.get((directory, name)) == data


BP.B.served = fake_served
BP.B.fetch = lambda host, directory, name, **k: node_of(host).serving.get((directory, name))
CISCO_9871 = b"""<CiscoIPPhoneImageList version="7.0">
<!-- Please Add Images to the end of the list-->
<ImageItem Name="DefaultWallpaper"
Image="TFTP:Desktops/DP-9871/wallpaper-syn12.png"
Thumbnail="TFTP:Desktops/DP-9871/thumbnail-syn12.png"
Theme = "dark"/>
<ImageItem Name="DefaultWallpaperV2"
Image="TFTP:Desktops/DP-9871/wallpaper-syn02.png"
Theme = "light"/>
<!--ImageItem Name="logo"
Image="TFTP:Desktops/DP-9871/logo.png"/-->
</CiscoIPPhoneImageList>
"""

app = maint_app.App()
app.update()
P = lambda: app.bg_panel                                         # noqa: E731 - rebuilt on a language switch
tab_texts = lambda: [app.nb.tab(t, "text").strip("‫‬‏") for t in app.nb.tabs()]   # noqa: E731


def settle(cond, secs=30):
    end = time.time() + secs
    while time.time() < end:
        app.update()
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("timed out")


def picker_rows():
    t = P().picker.tree
    return {i: t.set(i, "status") for i in t.get_children()}


assert tab_texts()[4:7] == ["MACD", "Phone Serials", "Phone Backgrounds"], tab_texts()

# ---- every text on the tab has Arabic
import ast
src = open(BP.__file__, encoding="utf-8").read()
keys = set()
for node in ast.walk(ast.parse(src)):
    if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_" and node.args and \
            isinstance(node.args[0], ast.Constant):
        keys.add(node.args[0].value)
    if isinstance(node, ast.Call) and getattr(node.func, "attr", "") in ("_message", "task") and \
            isinstance(node.args[0], ast.Constant):
        keys.add(node.args[0].value)
    if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "ui" and len(node.args) > 1 and \
            getattr(node.args[0], "attr", "") == "_message":
        keys.add(node.args[1].value)
keys |= {label for _v, label in BP.FITS + BP.THEMES} | set(BP.SERIES_HEAD.values()) | {"Phone Backgrounds"}
missing = sorted(k for k in keys if k not in i18n.AR)
assert len(keys) > 45 and not missing, missing

# ---- adding pictures: file names become letters and digits, and stay unique
BP.filedialog.askopenfilenames = lambda **k: paths
P().add_pictures()
assert [p["name"] for p in app.bg_state["pictures"]] == ["CompanyLogo", "beach", "CompanyLogo2"], app.bg_state
P().add_pictures()                                              # the same files again are not added twice
assert len(app.bg_state["pictures"]) == 3
P().lb.selection_clear(0, "end"); P().lb.selection_set(1); P()._picked()
app.v_bg_name.set("Beach Day!")
P()._rename()
assert app.bg_state["pictures"][1]["name"] == "BeachDay"
app.v_bg_name.set("Head.Office.png")                             # a dot inside a typed name is not an extension
P()._rename()
assert app.bg_state["pictures"][1]["name"] == "HeadOffice", app.bg_state["pictures"][1]
app.v_bg_name.set("BeachDay")
P()._rename()
assert app.bg_state["pictures"][1]["name"] == "BeachDay"
assert B.clean_name("C:/x/Very Long Photo Name From The Camera 2026.jpg", max_len=16) == "VeryLongPhotoNam"
P().c_theme.set("Dark"); P()._theme_picked()
assert app.bg_state["pictures"][1]["theme"] == "dark"
assert P()._photos, "preview shows the selected picture"
P().lb.selection_clear(0, "end"); P().lb.selection_set(2); P()._picked()
P().remove_picture()
assert [p["name"] for p in app.bg_state["pictures"]] == ["CompanyLogo", "BeachDay"]

# ---- checks before anything is built
for m in B.MODELS:
    BP.model_var(app, m[0]).set(False)
P()._models_changed()
P().save_zip()
assert said[-1] == "Tick at least one phone model."
for k in ("7945", "7941", "8800", "8875", "9851", "9871"):
    BP.model_var(app, k).set(True)
P()._models_changed()
assert P().c_prev.cget("values")[0] == "7941 · 7942 · 7961 · 7962"
saved_pics = list(app.bg_state["pictures"])
app.bg_state["pictures"] = saved_pics + [{"path": paths[0], "name": f"x{i}", "theme": "light"} for i in range(9)]
P().save_zip()
assert said[-1] == "9851 phones show at most 10 pictures; 11 are in the list.", said[-1]
app.bg_state["pictures"] = saved_pics

# ---- save as ZIP: one folder per model, pictures at the model's sizes, List.xml
zpath = os.path.join(_tmp, "out.zip")
BP.filedialog.asksaveasfilename = lambda **k: zpath
n_said = len(said)
P().save_zip()
settle(lambda: not app.busy)
assert len(said) == n_said, said[n_said:]   # no error dialog
assert P().lbl_msg.cget("text") == "Saved 30 files to out.zip", P().lbl_msg.cget("text")
z = zipfile.ZipFile(zpath)
names = sorted(z.namelist())
assert "Desktops/800x480x24/CompanyLogo.png" in names and "Desktops/800x480x24/TN-BeachDay.png" in names
assert "Desktops/DP-9871/wallpaper-BeachDay.png" in names and "Desktops/DP-9871/thumbnail-CompanyLogo.png" in names
assert len(names) == 6 * 5, names                                # 6 models x (2 pictures x 2 + List.xml)
size = lambda n: Image.open(io.BytesIO(z.read(n))).size          # noqa: E731
assert size("Desktops/1024x600x24/wallpaper-CompanyLogo.png") == (1024, 600)
assert size("Desktops/1024x600x24/thumbnail-BeachDay.png") == (180, 100)
lx = z.read("Desktops/1024x600x24/List.xml").decode()
assert 'Thumbnail="TFTP:Desktops/1024x600x24/thumbnail-BeachDay.png"' in lx and 'Theme="dark"' in lx and 'version="1.0"' in lx, lx
assert size("Desktops/320x212x16/CompanyLogo.png") == (320, 212) and size("Desktops/320x212x16/TN-BeachDay.png") == (80, 53)
assert size("Desktops/320x196x4/BeachDay.png") == (320, 196)
assert Image.open(io.BytesIO(z.read("Desktops/320x196x4/BeachDay.png"))).mode in ("P", "L")
assert size("Desktops/DP-9851/wallpaper-CompanyLogo.png") == (480, 240)
assert size("Desktops/DP-9871/wallpaper-BeachDay.png") == (1280, 720)
assert size("Desktops/DP-9871/thumbnail-BeachDay.png") == (228, 128)
lx = z.read("Desktops/DP-9871/List.xml").decode()
assert '<CiscoIPPhoneImageList version="1.0">' in lx and 'Name="BeachDay"' in lx and 'Theme="dark"' in lx and \
    'Thumbnail="TFTP:Desktops/DP-9871/thumbnail-BeachDay.png"' in lx, lx
lx = z.read("Desktops/800x480x24/List.xml").decode()
assert 'Image="TFTP:Desktops/800x480x24/TN-CompanyLogo.png" URL="TFTP:Desktops/800x480x24/CompanyLogo.png"' in lx, lx
import xml.dom.minidom
for n in names:
    if n.endswith("List.xml"):
        xml.dom.minidom.parseString(z.read(n))                    # well-formed
z.close()

# ---- save to folder: the TFTP layout under <folder>\Desktops
out_dir = os.path.join(_tmp, "folder")
os.makedirs(out_dir)
BP.filedialog.askdirectory = lambda **k: out_dir
P().save_folder()
settle(lambda: not app.busy)
assert len(said) == n_said, said[n_said:]
assert os.path.isfile(os.path.join(out_dir, "Desktops", "DP-9851", "List.xml"))
assert 'version="2.0"' in open(os.path.join(out_dir, "Desktops", "DP-9851", "List.xml")).read()   # goes up each time

# ---- upload: only CUCM nodes are offered; login + token on each, every file, TFTP restart, served check
app.nodes = [{"host": "10.9.0.1", "hostname": "pub", "type": "CUCM", "role": "Publisher", "cluster": "cucm"},
             {"host": "10.9.0.2", "hostname": "sub", "type": "CUCM", "role": "Subscriber", "cluster": "cucm"},
             {"host": "10.9.0.3", "hostname": "imp", "type": "IM&P", "role": "Subscriber", "cluster": "cucm"},
             {"host": "10.9.0.4", "hostname": "cuc", "type": "Unity", "role": "Publisher", "cluster": "cuc"}]
app._nodes_changed()
assert sorted(picker_rows()) == ["10.9.0.1", "10.9.0.2"], picker_rows()
P().upload()
assert "OS (platform) administrator" in said[-1], said[-1]      # no OS admin login typed yet
app.v_osuser.set("osadmin")
app.v_ospw.set("Platform#1")
P().upload()                                                     # restart ticked but no AXL user: said first
assert "needs the AXL user and password on the Cluster tab" in said[-1], said[-1]
app.v_axluser.set("axluser")
app.v_axlpw.set("AxlPw#1")
P().upload()                                                     # "No" in the confirmation: nothing happens
assert "Desktops/DP-9871" in said[-1] and "10.9.0.2" in said[-1] and not cucm
node_of("10.9.0.2").server_name = "10.9.0.2"                    # CUCM knows this one by its IP, not hostname
node_of("10.9.0.2").status_needs_empty = True                   # and takes only an empty status list
answers.append(True)
P().upload()
settle(lambda: not app.busy, 60)
for host in ("10.9.0.1", "10.9.0.2"):
    node = cucm[host]
    assert len(node.files) == 30 and node.restarts == ["restart Cisco Tftp"] and node.polls == 1, (host, len(node.files), node.restarts)
    assert node.files[("Desktops/DP-9871", "List.xml")].startswith(b'<CiscoIPPhoneImageList version="3.0">')
    assert picker_rows()[host].startswith("✓ uploaded; phones get"), picker_rows()
assert "10.9.0.3" not in cucm and "10.9.0.4" not in cucm
day_log = open(os.path.join(maint_app.LOG_DIR, sorted(os.listdir(maint_app.LOG_DIR))[-1]), encoding="utf-8").read()
assert "[10.9.0.1] Serviceability API took the restart for server name 'pub'" in day_log
assert "[10.9.0.2] Serviceability API took the restart for server name '10.9.0.2'" in day_log
assert "[10.9.0.2] Cisco Tftp restarted (Serviceability API reports Started)" in day_log
assert P().lbl_msg.cget("text") == "Uploaded to 2 of 2 TFTP servers", repr(P().lbl_msg.cget("text"))

# ---- without the restart, TFTP still serves the old list: said so, not a failure
app.v_bg_restart.set(False)
answers.append(True)
P().upload()
settle(lambda: not app.busy, 60)
assert cucm["10.9.0.1"].restarts == ["restart Cisco Tftp"]
assert "restart Cisco TFTP" in picker_rows()["10.9.0.1"], picker_rows()

# ---- wrong OS admin password on one node: that node fails, the other is uploaded
cucm["10.9.0.2"].password = "other"
app.v_bg_restart.set(True)
answers.append(True)
P().upload()
settle(lambda: not app.busy, 60)
assert picker_rows()["10.9.0.2"].startswith("✗ 10.9.0.2: OS Administration login refused"), picker_rows()
assert picker_rows()["10.9.0.1"].startswith("✓"), picker_rows()
assert "Upload failed on 1 TFTP server(s)" in said[-1], said[-1]

# ---- TFTP restart through the Serviceability API: a refused restart is reported as such, the files stay uploaded
cucm["10.9.0.2"].password = "Platform#1"
cucm["10.9.0.2"].tftp_state = "not active"
cucm["10.9.0.1"].restart_fault = "Service Cisco Tftp: Restart not allowed now"
n_restarts = len(cucm["10.9.0.1"].restarts)
answers.append(True)
P().upload()
settle(lambda: not app.busy, 60)
assert picker_rows()["10.9.0.1"] == "✗ uploaded, but Cisco TFTP did not restart", picker_rows()
assert picker_rows()["10.9.0.2"] == "✓ uploaded; Cisco TFTP is not activated on this node", picker_rows()
assert cucm["10.9.0.1"].restarts[n_restarts:] == ["restart Cisco Tftp"]
assert "files are uploaded, but Cisco TFTP did not restart on 1 node(s)" in said[-1], said[-1]
day_log = open(os.path.join(maint_app.LOG_DIR, sorted(os.listdir(maint_app.LOG_DIR))[-1]), encoding="utf-8").read()
assert "CUCM replied:\n" in day_log and "Restart not allowed now" in day_log, day_log[-800:]
assert "uploaded to 2/2 TFTP server(s), Cisco TFTP restart failed on 1" in day_log
assert "Cisco Tftp is not activated on this node (Stopped - Service Not Activated)" in day_log, day_log[-1500:]
del cucm["10.9.0.1"].restart_fault, cucm["10.9.0.2"].tftp_state
# a wrong AXL password: the API answers 401, reported with what to do; the files are still uploaded
app.v_axlpw.set("wrong")
answers.append(True)
P().upload()
settle(lambda: not app.busy, 60)
assert picker_rows()["10.9.0.1"] == "✗ uploaded, but Cisco TFTP did not restart", picker_rows()
assert "may not use the Serviceability API (HTTP 401)" in open(os.path.join(maint_app.LOG_DIR, sorted(
    os.listdir(maint_app.LOG_DIR))[-1]), encoding="utf-8").read()
app.v_axlpw.set("AxlPw#1")

# ---- Cisco's default PhoneOS list on the server: kept, comments too, ours added after it, version above the server's
cucm["10.9.0.2"].password = "Platform#1"
for host in ("10.9.0.1", "10.9.0.2"):
    node_of(host).serving[("Desktops/DP-9871", "List.xml")] = CISCO_9871
node_of("10.9.0.2").serving[("Desktops/320x212x16", "List.xml")] = b"<CiscoIPPhoneImageList><ImageItem Image='broken"
answers.append(True)
P().upload()
assert "already lists stay" in said[-1], said[-1]
settle(lambda: not app.busy, 60)
lx = cucm["10.9.0.1"].files[("Desktops/DP-9871", "List.xml")].decode()
import xml.dom.minidom
items = xml.dom.minidom.parseString(lx).getElementsByTagName("ImageItem")
assert [i.getAttribute("Name") for i in items] == ["DefaultWallpaper", "DefaultWallpaperV2", "CompanyLogo", "BeachDay"], lx
assert lx.startswith('<CiscoIPPhoneImageList version="8.0">') and "Please Add Images to the end of the list" in lx, lx
assert '<!--ImageItem Name="logo"' in lx and items[1].getAttribute("Thumbnail") == "" and items[0].getAttribute("Theme") == "dark"
assert picker_rows()["10.9.0.1"].startswith("✓"), picker_rows()
assert "not valid XML" in picker_rows()["10.9.0.2"] and "Desktops/320x212x16" in picker_rows()["10.9.0.2"], picker_rows()
said.pop()                                                       # "Upload failed on 1 TFTP server(s)"
# uploading again does not list the same pictures twice
answers.append(True)
P().upload()
settle(lambda: not app.busy, 60)
lx2 = cucm["10.9.0.1"].files[("Desktops/DP-9871", "List.xml")].decode()
assert lx2.count('Name="CompanyLogo"') == 1 and lx2.count('Name="DefaultWallpaper"') == 1, lx2
assert lx2.startswith('<CiscoIPPhoneImageList version="9.0">'), lx2[:60]
# untick Keep: the server's list is replaced by ours alone
app.v_bg_keep.set(False)
answers.append(True)
P().upload()
assert "is replaced" in said[-1]
settle(lambda: not app.busy, 60)
lx3 = cucm["10.9.0.1"].files[("Desktops/DP-9871", "List.xml")].decode()
assert "DefaultWallpaper" not in lx3 and lx3.count("<ImageItem") == 2, lx3
app.v_bg_keep.set(True)
# 79XX / 88XX lists: the same file again is replaced, others are kept
m = B.model("7945")
old = (b'<CiscoIPPhoneImageList><ImageItem Image="TFTP:Desktops/320x212x16/TN-Old.png" URL="TFTP:Desktops/320x212x16/Old.png"/>'
       b'<ImageItem Image="TFTP:Desktops/320x212x16/TN-A.png" URL="TFTP:Desktops/320x212x16/A.png"/></CiscoIPPhoneImageList>')
merged, kept = B.merge_list(m, old, B.list_xml(m, [("A", "light")]))
assert kept == 1 and merged.decode().count("URL=") == 2 and merged.decode().index("Old.png") < merged.decode().index("/A.png")
assert not merged.decode().startswith("<CiscoIPPhoneImageList version")

# ---- Arabic: the tab, the picture list, the ticks and the theme survive the switch
app.lang_cb.set(i18n.LANGUAGES["ar"])
app._language_picked()
app.update()
assert "خلفيات الهواتف" in tab_texts() and "Phone Backgrounds" not in tab_texts(), tab_texts()
assert P().lb.size() == 2 and BP.model_var(app, "9871").get() and not BP.model_var(app, "9861").get()
assert P().c_prev.cget("values")[0] == "7941 · 7942 · 7961 · 7962"
P().lb.selection_clear(0, "end"); P().lb.selection_set(1); P()._picked()
assert P().c_theme.get() == i18n._("Dark") and "داكن" in P().c_theme.get()
assert sorted(picker_rows()) == ["10.9.0.1", "10.9.0.2"]
app.lang_cb.set(i18n.LANGUAGES["en"])
app._language_picked()
app.update()

# ---- settings: pictures, ticks and the List.xml version are saved; no password
app._save_cfg()
cfg = json.load(open(maint_app.CONFIG, encoding="utf-8"))
bg = cfg["backgrounds"]
assert [p["name"] for p in bg["pictures"]] == ["CompanyLogo", "BeachDay"] and bg["list_version"] == 10 and bg["keep"] is True, bg
assert sorted(bg["models"]) == sorted(["7941", "7945", "8800", "8875", "9851", "9871"]) and bg["fit"] == "fill"
assert "Platform#1" not in json.dumps(cfg)

# ---- PhoneOS logo: logo.png in each PhoneOS folder, scaled in proportion, transparency kept, Name="logo"
logo_path = os.path.join(pics_dir, "Company Logo Transparent.png")
lg = Image.new("RGBA", (1000, 400), (0, 0, 0, 0))
lg.paste((14, 124, 134, 255), (100, 100, 900, 300))
lg.save(logo_path)
assert P().lbl_logo.cget("text") == "none" and "disabled" in P().btn_nologo.state()
BP.filedialog.askopenfilename = lambda **k: logo_path
P().choose_logo()
assert app.bg_state["logo"] == os.path.normpath(logo_path) and P().lbl_logo.cget("text") == "Company Logo Tr…"
zpath2 = os.path.join(_tmp, "logo.zip")
BP.filedialog.asksaveasfilename = lambda **k: zpath2
n_said = len(said)
P().save_zip()
settle(lambda: not app.busy)
assert len(said) == n_said, said[n_said:]
z = zipfile.ZipFile(zpath2)
lim = Image.open(io.BytesIO(z.read("Desktops/DP-9871/logo.png")))
assert lim.size == (494, 198) and lim.mode == "RGBA" and lim.getpixel((0, 0))[3] == 0, (lim.size, lim.mode)
assert Image.open(io.BytesIO(z.read("Desktops/1024x600x24/logo.png"))).size == (380, 152)
assert Image.open(io.BytesIO(z.read("Desktops/DP-9851/logo.png"))).size == (190, 76)
assert "Desktops/320x212x16/logo.png" not in z.namelist() and "Desktops/800x480x24/logo.png" not in z.namelist()
lx = z.read("Desktops/DP-9871/List.xml").decode()
assert lx.rstrip().endswith('<ImageItem Name="logo" Image="TFTP:Desktops/DP-9871/logo.png"/>\r\n</CiscoIPPhoneImageList>'), lx
assert "logo" not in z.read("Desktops/320x212x16/List.xml").decode()
z.close()
# a logo on its own: fine for PhoneOS models only
saved_pics = app.bg_state["pictures"]
app.bg_state["pictures"] = []
P().save_zip()
assert said[-1] == "7941 · 7942 · 7961 · 7962 phones have no logo: add at least one picture for them.", said[-1]
ticks = {m[0]: BP.model_var(app, m[0]).get() for m in B.MODELS}
for m in B.MODELS:
    BP.model_var(app, m[0]).set(m[0] in ("9861", "8875"))
n_said = len(said)
P().save_zip()
settle(lambda: not app.busy)
assert len(said) == n_said, said[n_said:]
names = zipfile.ZipFile(zpath2).namelist()
assert sorted(names) == ["Desktops/1024x600x24/List.xml", "Desktops/1024x600x24/logo.png",
                         "Desktops/DP-9861/List.xml", "Desktops/DP-9861/logo.png"], names
for k, v in ticks.items():
    BP.model_var(app, k).set(v)
app.bg_state["pictures"] = saved_pics
# merging: our logo replaces a logo entry already there; Cisco's commented-out one stays a comment
m = B.model("9861NR")
server = (b'<CiscoIPPhoneImageList version="2.0"><ImageItem Name="Old" Image="TFTP:Desktops/DP-9861NR/wallpaper-Old.png"/>'
          b'<ImageItem Name="logo" Image="TFTP:Desktops/DP-9861NR/oldlogo.png"/>'
          b'<!--ImageItem Name="logo"\nImage="TFTP:Desktops/DP-9861NR/logo.png"/--></CiscoIPPhoneImageList>')
merged, kept = B.merge_list(m, server, B.list_xml(m, [("A", "light")], "1.0", logo=True))
merged = merged.decode()
assert kept == 1 and "oldlogo.png" not in merged and merged.count('Name="logo" Image=') == 1, merged
assert '<!--ImageItem Name="logo"' in merged and merged.startswith('<CiscoIPPhoneImageList version="3.0">'), merged
app._save_cfg()
assert json.load(open(maint_app.CONFIG, encoding="utf-8"))["backgrounds"]["logo"] == os.path.normpath(logo_path)
P().remove_logo()
assert app.bg_state["logo"] is None and P().lbl_logo.cget("text") == "none"

# ---- Rename all: one short name, numbered; Cancel changes nothing
BP.simpledialog.askstring = lambda *a, **k: None
P().rename_all()
assert [p["name"] for p in app.bg_state["pictures"]] == ["CompanyLogo", "BeachDay"]
BP.simpledialog.askstring = lambda *a, **k: "Office Wall!"
P().rename_all()
assert [p["name"] for p in app.bg_state["pictures"]] == ["OfficeWall1", "OfficeWall2"], app.bg_state["pictures"]
assert P().lb.get(0).startswith("OfficeWall1") and "Company Logo.jpg" in P().lb.get(0)
assert [p["name"] for p in json.load(open(maint_app.CONFIG, encoding="utf-8"))["backgrounds"]["pictures"]] ==     ["OfficeWall1", "OfficeWall2"]                               # saved straight away
built = B.build(app.bg_state["pictures"], ["8875", "7945"])
assert [n for n, _d in built["Desktops/1024x600x24"]][:2] == ["wallpaper-OfficeWall1.png", "thumbnail-OfficeWall1.png"]
assert [n for n, _d in built["Desktops/320x212x16"]][:2] == ["OfficeWall1.png", "TN-OfficeWall1.png"]
app.destroy()

# ---- the real uploader reads the token and refuses a page without "uploaded successfully"
up = B.TftpUploader("h", "osadmin", "Platform#1", session=FakeSession("h"))
node_of("h").password = "Platform#1"
up.login()
assert up.token == "TOK1"
up.token = "stale"
try:
    up.upload("Desktops/x", "a.png", b"1")
    raise AssertionError("stale token accepted")
except B.BackgroundError as e:
    assert "Submit twice" in str(e), e
assert up.token == "TOK2"                                         # the error page's new token is kept
assert up.upload("Desktops/x", "a.png", b"1") and node_of("h").files[("Desktops/x", "a.png")] == b"1"
print("phone backgrounds tab: all checks passed")
