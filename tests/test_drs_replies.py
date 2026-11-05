"""DRS handling of CUCM's real replies (wording taken from a CUCM 12.5 lab), and exclusive use of
the SFTP port. No CUCM or GUI needed."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cucm_ops as ops
from cucm_cli import CLIError
from sftp_server import SFTPServer

IN_PROGRESS = ("drfCliMsg: BACKUP operation currently in progress....For the latest information on the state of "
               "the system, please use the 'utils disaster_recovery status Backup/Restore' command\n\n"
               "Executed command unsuccessfully")
SAVED = "drfCliMsg: Backup Device has been saved successfully."
STARTED = ("drfCliMsg: Backup initiated successfully. Please run 'utils disaster_recovery status backup' "
           "command to see the status")


class Shell:
    """Answers each run() with the next canned reply."""
    host = "10.0.0.1"

    def __init__(self, *replies):
        self.replies, self.cmds = list(replies), []

    def log(self, msg):
        pass

    def run(self, cmd, **kw):
        self.cmds.append(cmd)
        return self.replies.pop(0)


def raises(fn, *a, text="", **k):
    try:
        fn(*a, **k)
    except CLIError as e:
        assert text in str(e), str(e)
        return True
    raise AssertionError("no error raised")


def status(tar, percent, state="SUCCESS :Backup Completed..."):
    return (f"Status: {state}\nTar Filename: {tar}\nStorage Location: NETWORK\nOperation: backup\n"
            f"Percentage Complete: {percent}\n"
            f"UCM   CUCMPUB   CCMDB   SUCCESS   Tue Oct 27 14:14:12 GST 2026   activelog/x.log\n")


# ---- saving the device
assert ops.drs_add_device(Shell(SAVED), "BK", "/backup", "10.1.1.1", "u", "p") == SAVED
raises(ops.drs_add_device, Shell(IN_PROGRESS), "BK", "/backup", "10.1.1.1", "u", "p", text="in progress")
raises(ops.drs_add_device, Shell("Unable to connect to server 10.1.1.1"), "BK", "/backup", "10.1.1.1", "u", "p",
       text="did not save")
raises(ops.drs_add_device, Shell("some unknown reply"), "BK", "/backup", "10.1.1.1", "u", "p", text="did not save")
sh = Shell("Device already exists", "deleted", SAVED)
assert ops.drs_add_device(sh, "BK", "/backup", "10.1.1.1", "u", "p") == SAVED
assert "device delete BK" in sh.cmds[1] and "device add" in sh.cmds[2]

# ---- starting the backup
assert "initiated" in ops.drs_start_backup(Shell(STARTED), "UCM,CDR_CAR", "BK")
raises(ops.drs_start_backup, Shell(IN_PROGRESS), "UCM", "BK", text="did not start")
raises(ops.drs_start_backup, Shell("Executed command unsuccessfully"), "UCM", "BK", text="did not start")

# ---- status: real components parse; a success below 100 % is not the end
st = ops.drs_status(Shell(status("old.tar", 100)))
assert (st["tar"], st["percent"], st["components"][0][2:]) == ("old.tar", 100, ["CCMDB", "SUCCESS"])
assert ops.drs_finished(st)
assert not ops.drs_finished(ops.drs_status(Shell(status("new.tar", 40, "SUCCESS")))), "40 % is still running"
assert ops.drs_finished(ops.drs_status(Shell(status("new.tar", 40, "ERROR"))))

# ---- following: the previous backup's result is not reported as the new one
seen = []
sh = Shell(status("old.tar", 100), status("old.tar", 100), status("new.tar", 30, "IN PROGRESS"), status("new.tar", 100))
ops.time.sleep, real_sleep = (lambda s: None), ops.time.sleep
end = ops.drs_wait(sh, poll=1, on_status=lambda s: seen.append(s["tar"]), previous_tar="old.tar")
ops.time.sleep = real_sleep
assert end["tar"] == "new.tar" and end["percent"] == 100 and "old.tar" not in seen, seen
raises(ops.drs_wait, Shell(status("old.tar", 100)), poll=1, previous_tar="old.tar", grace=-1, text="previous one")

# ---- other commands reading the same reply
assert ops.REFUSED.search(IN_PROGRESS) and not ops.SUCCEEDED.search("Executed command unsuccessfully")

# ---- SFTP port: a second server gets a clear error, and a restart works
tmp = tempfile.mkdtemp()
a = SFTPServer(os.path.join(tmp, "a"), "u", "password1", port=2097, bind="127.0.0.1", host_key_path=os.path.join(tmp, "k1"))
b = SFTPServer(os.path.join(tmp, "b"), "u", "password2", port=2097, bind="127.0.0.1", host_key_path=os.path.join(tmp, "k1"))
a.start()
try:
    b.start()
    raise AssertionError("second server shared the port")
except OSError as e:
    assert "CallBill" in str(e), e
a.stop()
b.start()          # free again right after the stop
b.stop()
print("DRS REPLIES OK")
