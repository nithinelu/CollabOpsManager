"""The SFTP login given to CUCM always works on the running server, even after the boxes were edited,
and sftp_params' own error messages show. Real SFTP logins on localhost; no CUCM or window needed."""
import os
import sys
import tempfile
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paramiko

import maint_app
from cucm_cli import CLIError
from sftp_server import SFTPServer

PORT = 2098


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def can_login(user, password):
    t = paramiko.Transport(("127.0.0.1", PORT))
    try:
        t.connect(username=user, password=password)
        paramiko.SFTPClient.from_transport(t).listdir("/")
        return True
    except paramiko.AuthenticationException:
        return False
    finally:
        t.close()


tmp = tempfile.mkdtemp()
server = SFTPServer(os.path.join(tmp, "root"), "firstuser", "firstpass1", port=PORT, bind="127.0.0.1",
                    host_key_path=os.path.join(tmp, "key"))
server.start()
ip = maint_app.local_ipv4_addresses()[0]
logs, ui_calls = [], []
app = NS(v_ip=Var(ip), v_pub=Var(""), v_cucpub=Var(""), v_port=Var(str(PORT)), v_suser=Var("firstuser"),
         v_spw=Var("firstpass1"), _ip_auto=False, server=server, log=logs.append,
         ui=lambda fn, *a: ui_calls.append(fn), start_sftp=None, _sftp_running_ui=None)
params = maint_app.App.sftp_params

try:
    # ---- nothing edited: nothing changes
    assert params(app) == (ip, PORT, "firstuser", "firstpass1")
    assert not logs and not ui_calls

    # ---- edited while running: this was CUCM's "wrong username/password"
    app.v_spw.set("secondpass2")
    assert can_login("firstuser", "firstpass1"), "old login holds until the new one is handed out"
    assert params(app)[3] == "secondpass2"
    assert can_login("firstuser", "secondpass2")
    assert not can_login("firstuser", "firstpass1")
    assert ui_calls == [None], "the status line is refreshed"

    app.v_suser.set(" seconduser ")
    assert params(app)[2] == "seconduser"
    assert can_login("seconduser", "secondpass2")
    assert not can_login("firstuser", "secondpass2")
    assert not any("secondpass2" in m for m in logs), "password must not reach the log"

    # ---- an unusable login is refused and leaves the server alone
    app.v_spw.set("short")
    try:
        params(app)
        raise AssertionError("short password accepted")
    except CLIError as e:
        assert "6 characters" in str(e), e
    assert server.password == "secondpass2"
finally:
    server.stop()

# ---- error messages show as messages (a loop variable named _ used to break them)
app.v_spw.set("secondpass2")
app.server = None
real_event = maint_app.threading.Event
maint_app.threading.Event = lambda: NS(wait=lambda s: None)
try:
    params(app)
    raise AssertionError("no error with the server stopped")
except CLIError as e:
    assert "not running" in str(e), e
finally:
    maint_app.threading.Event = real_event

app.v_ip.set("")
try:
    params(app)
    raise AssertionError("no error with an empty IP")
except CLIError as e:
    assert "IP address" in str(e), e
print("SFTP LOGIN CHANGE OK")
