"""A client using another program's user name (such as a CUCM pushing CDR files as 'otherapp' to a
different SFTP server on this PC) is explained once in the log; its retries stay out of the log for an
hour. Wrong passwords for our own user and good logins are always logged."""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paramiko

import sftp_server

lines = []
tmp = tempfile.mkdtemp()
srv = sftp_server.SFTPServer(os.path.join(tmp, "root"), "cucmsftp", "secret123", port=2097, bind="127.0.0.1",
                             host_key_path=os.path.join(tmp, "k", "host.key"), log=lines.append)
srv.start()


def login(user, pw):
    t = paramiko.Transport(("127.0.0.1", 2097))
    try:
        t.connect(username=user, password=pw)
        ok = True
    except paramiko.AuthenticationException:
        ok = False
    t.close()
    time.sleep(1.2)                           # the server notices the close and logs "disconnected"
    return ok


try:
    assert not login("otherapp", "x")
    first = [ln for ln in lines if "127.0.0.1" in ln]
    assert any("login FAILED for 'otherapp' - this server only accepts 'cucmsftp'" in ln and
               "not logged for the next hour" in ln for ln in first), first
    n = len(lines)
    assert not login("otherapp", "x") and not login("otherapp", "y")
    assert lines[n:] == [], lines[n:]                         # retries: no connected / FAILED / disconnected lines
    assert not login("cucmsftp", "wrong")
    assert any("login FAILED for 'cucmsftp' - wrong password" in ln for ln in lines[n:]), lines[n:]
    n = len(lines)
    assert login("cucmsftp", "secret123")
    assert any("login OK as 'cucmsftp'" in ln for ln in lines[n:]) and any("connected" in ln for ln in lines[n:])
    n = len(lines)
    assert not login("otheruser", "x")                         # a different foreign user is explained again
    assert any("login FAILED for 'otheruser'" in ln for ln in lines[n:]), lines[n:]
    # allowed IP list: a refused peer is logged once, then its retries are quiet
    srv.allowed_ips = {"10.0.0.1"}
    n = len(lines)
    for _ in range(3):
        try:
            login("otherapp", "x")
        except Exception:
            pass                                               # the server closes before SSH starts
    refused = [ln for ln in lines[n:] if "127.0.0.1" in ln]
    assert len(refused) == 1 and "connection refused - not a node of this cluster" in refused[0], refused
finally:
    srv.stop()
print("SFTP foreign login: all checks passed")
