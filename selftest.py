"""Build check: `CollabOpsManager.exe --selftest <report file>` runs the parts a one-file exe can
lose (crypto, SSH/SFTP, XML, Excel, DPAPI, Tk, Arabic) inside the exe, in a temp folder, without
touching config.json or any cluster. Writes one PASS/FAIL line per check; exit code 0 = all passed."""

import json
import os
import sys
import tempfile
import traceback


def _sftp(tmp):
    import paramiko
    from sftp_server import SFTPServer
    root = os.path.join(tmp, "sftp")
    srv = SFTPServer(root, "tester", "secret123", port=2099, bind="127.0.0.1",
                     host_key_path=os.path.join(tmp, "key", "host.key"))
    srv.start()
    try:
        t = paramiko.Transport(("127.0.0.1", 2099))
        t.connect(username="tester", password="secret123")
        s = paramiko.SFTPClient.from_transport(t)
        local = os.path.join(tmp, "up.bin")
        with open(local, "wb") as f:
            f.write(os.urandom(200_000))
        s.put(local, "/up.bin")
        assert s.stat("/up.bin").st_size == 200_000
        t.close()
    finally:
        srv.stop()
    return "server + client: 200 KB upload"


def _xml(tmp):
    from lxml import etree
    assert etree.fromstring(b"<a><b>1</b></a>").findtext("b") == "1"
    import axl_client
    assert axl_client.AXL_VERSIONS
    return "lxml + AXL client"


def _excel(tmp):
    from openpyxl import load_workbook
    import cucm_ops as ops
    path = os.path.join(tmp, "x.xlsx")
    ops.export_to_excel([("Sheet", "q")], lambda q: [{"a": "1"}], path, summary_sheet=False)
    assert load_workbook(path).sheetnames == ["Sheet"]
    return "write + read"


def _https(tmp):
    import requests
    import certifi
    assert requests.Session() and os.path.exists(certifi.where())
    return "requests + certifi"


def _dpapi(tmp):
    from secrets_store import protect, unprotect
    assert unprotect(protect("pässword")) == "pässword"
    return "encrypt + decrypt"


def _gui(tmp):
    import i18n
    import maint_app
    maint_app.CONFIG = os.path.join(tmp, "config.json")
    maint_app.LOG_DIR = os.path.join(tmp, "logs")
    maint_app.REPORT_DIR = os.path.join(tmp, "reports")
    with open(maint_app.CONFIG, "w", encoding="utf-8") as f:
        json.dump({"language": "en", "sftp_root": os.path.join(tmp, "root")}, f)
    app = maint_app.App()
    app.update()
    assert len(app.nb.tabs()) == 7 and app._logo.width() > 0
    assert os.path.exists(os.path.join(maint_app.RES, "LICENSE"))
    app.lang_cb.set(i18n.LANGUAGES["ar"])
    app._language_picked()
    app.update()
    assert app.rtl and len(app.macd_panel.tabs) == 5
    app.destroy()
    return "all tabs, logo, licence, Arabic switch"


def run(report):
    checks = (("SFTP", _sftp), ("XML / AXL", _xml), ("Excel", _excel), ("HTTPS", _https),
              ("DPAPI", _dpapi), ("Window", _gui))
    failed = 0
    with tempfile.TemporaryDirectory() as tmp, open(report, "w", encoding="utf-8") as out:
        out.write(f"frozen={getattr(sys, 'frozen', False)}\n")
        for name, fn in checks:
            try:
                out.write(f"PASS {name}: {fn(tmp)}\n")
            except Exception:
                failed += 1
                out.write(f"FAIL {name}:\n{traceback.format_exc()}\n")
            out.flush()
        out.write("RESULT " + ("OK" if not failed else f"{failed} FAILED") + "\n")
    return 1 if failed else 0
