"""CiscoIPPhoneSerialGrabber engine - read serial numbers (and MAC, model, DN, firmware) from Cisco IP phones.

How it works
  * Targets are single IPs, ranges (10.1.1.10-50 or 10.1.1.10-10.1.1.60), CIDR subnets or host names.
  * Optionally the target list is discovered from CUCM over RisPort70 (registered phones and their IPs).
  * Each target gets a quick TCP check on 80/443, then the phone's own web server is read:
      1. /DeviceInformationX               (XML - 69xx/78xx/79xx/88xx/89xx/99xx/DX/conference phones)
      2. /CGI/Java/Serviceability?adapter=device.statistics.device, /DeviceInformation, /   (HTML fallback,
         also covers older phones and the Multiplatform/3PCC "Info" page)
  * "Web Access" must be enabled on the phone (CUCM > Phone > Product Specific Configuration).

CLI:  py grabber_engine.py 10.10.20.0/24 10.10.21.5-80 -o phones.xlsx
      py grabber_engine.py --cucm 10.10.1.10 --user axluser -o phones.xlsx

Copyright (c) 2026 Nithin Eluvathingal. MIT License - see LICENSE.
"""

import argparse
import csv
import getpass
import html
import ipaddress
import os
import re
import socket
import sys
import threading
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_TARGETS = 65536

# Result columns: (key, heading, width) - shared by the GUI, CSV and Excel export.
COLUMNS = [
    ("ip", "IP Address", 110), ("status", "Status", 110), ("model", "Model", 110),
    ("serial", "Serial Number", 120), ("mac", "MAC Address", 130), ("hostname", "Device Name", 155),
    ("dn", "Phone DN", 90), ("firmware", "Firmware", 210), ("hw_rev", "HW Rev", 70),
    ("cucm_desc", "CUCM Description", 180), ("cucm_status", "CUCM Status", 105), ("source", "Source", 150),
    ("note", "Note", 260),
]

ST_OK = "OK"
ST_PARTIAL = "No serial"
ST_NOWEB = "Web closed"
ST_NOTPHONE = "Not a phone"
ST_DOWN = "No response"
ST_ERROR = "Error"


# ----------------------------------------------------------------------------------------------- targets
def parse_targets(text):
    """Return (list of target strings, list of error lines). Accepts IPs, ranges, CIDR and host names,
    separated by new lines, commas, semicolons or spaces. '#' starts a comment."""
    targets, errors, seen = [], [], set()

    def add(t):
        if t not in seen:
            seen.add(t)
            targets.append(t)

    for raw in text.splitlines():
        line = raw.split("#", 1)[0]
        for tok in re.split(r"[,\s;]+", line):
            tok = tok.strip()
            if not tok:
                continue
            try:
                for t in _expand(tok):
                    add(t)
                    if len(targets) > MAX_TARGETS:
                        raise ValueError(f"more than {MAX_TARGETS} addresses - narrow the range")
            except ValueError as e:
                errors.append(f"{tok}: {e}")
                if len(targets) > MAX_TARGETS:
                    return targets[:MAX_TARGETS], errors
    return targets, errors


def _expand(tok):
    if "/" in tok:
        net = ipaddress.ip_network(tok, strict=False)
        if net.num_addresses > MAX_TARGETS:
            raise ValueError(f"subnet too large (max /{32 - 16})")
        hosts = list(net.hosts()) or [net.network_address]
        return [str(h) for h in hosts]
    if "-" in tok and re.match(r"^\d+\.\d+\.\d+\.\d+-", tok):
        start_s, end_s = tok.split("-", 1)
        start = ipaddress.ip_address(start_s)
        if re.fullmatch(r"\d{1,3}", end_s):
            end = ipaddress.ip_address(".".join(start_s.split(".")[:3] + [end_s]))
        else:
            end = ipaddress.ip_address(end_s)
        if int(end) < int(start):
            raise ValueError("range end is before range start")
        if int(end) - int(start) >= MAX_TARGETS:
            raise ValueError("range too large")
        return [str(ipaddress.ip_address(i)) for i in range(int(start), int(end) + 1)]
    try:
        return [str(ipaddress.ip_address(tok))]
    except ValueError:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.\-]*", tok):
            return [tok]  # host name
        raise ValueError("not an IP, range, subnet or host name")


def read_target_file(path):
    """Read targets from .txt/.csv (any IP-looking cells) or .xlsx (all cells)."""
    if path.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        cells = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                cells.extend(str(v) for v in row if v is not None)
        text = "\n".join(cells)
    else:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            text = f.read()
    # keep only things that look like IPs / ranges / subnets so headers and names are ignored
    found = re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2}|-\d{1,3}(?:\.\d{1,3}){0,3})?\b", text)
    return "\n".join(found)


# ----------------------------------------------------------------------------------------------- phone query
XML_PATH = "/DeviceInformationX"
HTML_PATHS = ["/CGI/Java/Serviceability?adapter=device.statistics.device", "/DeviceInformation", "/"]

# lower-cased XML tag -> result key
XML_MAP = {
    "serialnumber": "serial", "macaddress": "mac", "hostname": "hostname", "modelnumber": "model",
    "phonedn": "dn", "versionid": "firmware", "hardwarerevision": "hw_rev", "udi": "udi",
    "apploadid": "app_load",
}
# normalised HTML label -> result key (first label found wins)
HTML_LABELS = [
    ("serial number", "serial"), ("serial no", "serial"), ("serial", "serial"),
    ("mac address", "mac"), ("host name", "hostname"), ("hostname", "hostname"),
    ("model number", "model"), ("product name", "model"), ("model", "model"),
    ("phone dn", "dn"), ("version", "firmware"), ("software version", "firmware"),
    ("hardware revision", "hw_rev"), ("hardware version", "hw_rev"), ("udi", "udi"),
]


def _port_open(host, port, timeout):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def parse_xml_info(text):
    """Pull leaf values from DeviceInformationX. Regex based: phone XML is not always well-formed."""
    out = {}
    for tag, val in re.findall(r"<(\w+)>([^<]*)</\1>", text):
        key = XML_MAP.get(tag.lower())
        if key and key not in out and val.strip():
            out[key] = html.unescape(val).strip()
    return out


def _html_tokens(text):
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", "\n", text)
    toks = []
    for t in html.unescape(text).replace("\xa0", " ").splitlines():
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            toks.append(t)
    return toks


def parse_html_info(text):
    """Label/value scrape of a phone status page: value is the next non-empty text after the label."""
    toks = _html_tokens(text)
    norm = [re.sub(r"[\s:]+$", "", t).strip().lower() for t in toks]
    out = {}
    for label, key in HTML_LABELS:
        if key in out:
            continue
        for i, n in enumerate(norm):
            if n == label and i + 1 < len(toks):
                val = toks[i + 1].strip()
                # inline "Label: value" was split into one token - handled below
                if val and re.sub(r"[\s:]+$", "", val).lower() not in dict(HTML_LABELS):
                    out[key] = val
                    break
        else:
            for t in toks:  # "Serial Number: FCH1234ABCD" in one text node
                m = re.match(rf"(?i)^{re.escape(label)}\s*:\s*(\S.*)$", t)
                if m:
                    out[key] = m.group(1).strip()
                    break
    return out


def _clean(info):
    """Tidy fields and derive what can be derived."""
    udi = info.pop("udi", "")
    if udi and not info.get("serial"):
        parts = [p for p in re.split(r"[\s,]+", udi) if p]
        if parts and re.fullmatch(r"[A-Z]{3}\w{6,}", parts[-1]):
            info["serial"] = parts[-1]
    if udi and not info.get("model"):
        m = re.search(r"\b(CP-\S+|DX\d+\S*)", udi)
        if m:
            info["model"] = m.group(1)
    if not info.get("firmware") and info.get("app_load"):
        info["firmware"] = info["app_load"]
    info.pop("app_load", None)
    mac = re.sub(r"[^0-9A-Fa-f]", "", info.get("mac", ""))
    if not mac and re.fullmatch(r"(?i)SEP[0-9A-F]{12}", info.get("hostname", "")):
        mac = info["hostname"][3:]
    if len(mac) == 12:
        info["mac"] = mac.upper()
    for k in ("serial", "model", "dn", "firmware", "hw_rev", "hostname"):
        if k in info:
            info[k] = info[k].strip()
    return info


def query_phone(host, timeout=4.0, try_https=True, auth=None, session=None):
    """Return a result dict (see COLUMNS) for one target."""
    res = {"ip": host, "status": ST_DOWN, "source": "", "note": ""}
    connect_to = min(timeout, 2.0)
    ports = [("http", 80)] + ([("https", 443)] if try_https else [])
    open_schemes = [s for s, p in ports if _port_open(host, p, connect_to)]
    if not open_schemes:
        res["note"] = "TCP 80/443 closed or host down" if try_https else "TCP 80 closed or host down"
        return res

    s = session or requests.Session()
    s.verify = False
    hdrs = {"User-Agent": "CiscoIPPhoneSerialGrabber/1.0"}
    info, source, last_err, saw_http = {}, "", "", False

    def get(url):
        return s.get(url, timeout=timeout, headers=hdrs, auth=auth, allow_redirects=True)

    for scheme in open_schemes:
        base = f"{scheme}://{host}"
        try:
            r = get(base + XML_PATH)
            saw_http = True
            if r.status_code == 200 and re.search(r"(?i)<(serialNumber|MACAddress)>", r.text):
                info = parse_xml_info(r.text)
                source = f"{r.url.split('://')[0]} XML"
                break
            if r.status_code == 401:
                last_err = "web page needs a login (HTTP 401) - enter credentials"
        except requests.RequestException as e:
            last_err = _short_err(e)
        if info:
            break
        for path in HTML_PATHS:
            try:
                r = get(base + path)
                saw_http = True
            except requests.RequestException as e:
                last_err = _short_err(e)
                continue
            if r.status_code == 401:
                last_err = "web page needs a login (HTTP 401) - enter credentials"
                continue
            if r.status_code != 200:
                continue
            got = parse_html_info(r.text)
            if got.get("serial") or (got.get("mac") and (got.get("model") or got.get("hostname"))):
                info, source = got, f"{r.url.split('://')[0]} {path.split('?')[0]}"
                break
        if info:
            break

    if not info:
        if saw_http:
            res["status"] = ST_NOTPHONE
            res["note"] = last_err or "web server answered but no Cisco phone info page found"
        else:
            res["status"] = ST_NOWEB
            res["note"] = last_err or "port open but HTTP failed"
        return res

    res.update(_clean(info))
    res["source"] = source
    res["status"] = ST_OK if res.get("serial") else ST_PARTIAL
    if not res.get("serial"):
        res["note"] = "phone answered but did not report a serial number"
    return res


def _short_err(e):
    msg = str(e)
    if "timed out" in msg.lower() or isinstance(e, requests.Timeout):
        return "HTTP timed out"
    if "refused" in msg.lower():
        return "connection refused"
    m = re.search(r"\]\s*([^\]')]+)", msg)
    return (m.group(1) if m else msg)[:120]


def scan(targets, workers=64, timeout=4.0, try_https=True, auth=None, stop_event=None, on_result=None,
         extra=None):
    """Query all targets in parallel. on_result(result, done, total) is called from worker threads.
    extra: {ip: {cucm fields}} merged into each result. Returns the list of results (target order)."""
    stop_event = stop_event or threading.Event()
    extra = extra or {}
    results = {}
    total = len(targets)
    done = 0
    lock = threading.Lock()
    tls = threading.local()

    def work(t):
        if stop_event.is_set():
            return None
        if not hasattr(tls, "s"):
            tls.s = requests.Session()
        try:
            r = query_phone(t, timeout=timeout, try_https=try_https, auth=auth, session=tls.s)
        except Exception as e:  # never let one target kill the scan
            r = {"ip": t, "status": ST_ERROR, "note": str(e)[:200]}
        r.update({k: v for k, v in extra.get(t, {}).items() if v and not r.get(k)})
        return r

    with ThreadPoolExecutor(max_workers=max(1, min(workers, 256))) as ex:
        futs = {ex.submit(work, t): t for t in targets}
        for f in as_completed(futs):
            r = f.result()
            if r is None:
                continue
            with lock:
                done += 1
                results[futs[f]] = r
            if on_result:
                on_result(r, done, total)
            if stop_event.is_set():
                for g in futs:
                    g.cancel()
    return [results[t] for t in targets if t in results]


# ----------------------------------------------------------------------------------------------- CUCM RisPort70
RIS_PATH = "/realtimeservice2/services/RISService70"
RIS_BODY = """<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:soap="http://schemas.cisco.com/ast/soap"><soapenv:Header/><soapenv:Body>
<soap:selectCmDeviceExt><soap:StateInfo>{state}</soap:StateInfo><soap:CmSelectionCriteria>
<soap:MaxReturnedDevices>{maxn}</soap:MaxReturnedDevices><soap:DeviceClass>Phone</soap:DeviceClass>
<soap:Model>255</soap:Model><soap:Status>{status}</soap:Status><soap:NodeName></soap:NodeName>
<soap:SelectBy>Name</soap:SelectBy><soap:SelectItems>{items}</soap:SelectItems>
<soap:Protocol>Any</soap:Protocol><soap:DownloadStatus>Any</soap:DownloadStatus>
</soap:CmSelectionCriteria></soap:selectCmDeviceExt></soapenv:Body></soapenv:Envelope>"""

AXL_VERSIONS = ["15.0", "14.0", "12.5", "12.0", "11.5", "11.0", "10.5", "10.0", "9.1", "9.0"]
AXL_LIST_PHONE = """<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:ns="http://www.cisco.com/AXL/API/{ver}"><soapenv:Header/><soapenv:Body><ns:listPhone>
<searchCriteria><name>%</name></searchCriteria><returnedTags><name/></returnedTags>
<skip>{skip}</skip><first>{first}</first></ns:listPhone></soapenv:Body></soapenv:Envelope>"""


class CucmError(Exception):
    pass


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _child_text(el, name):
    for c in el:
        if _local(c.tag) == name:
            return (c.text or "").strip()
    return ""


def parse_ris(xml_text):
    """Return (devices, state_info). devices: list of dicts with name, ip, dn, desc, status, httpd, model_id."""
    root = ET.fromstring(xml_text)
    fault = next((e for e in root.iter() if _local(e.tag) == "faultstring"), None)
    if fault is not None:
        raise CucmError(f"RisPort fault: {fault.text}")
    devices = []
    for cmdevs in (e for e in root.iter() if _local(e.tag) == "CmDevices"):
        for item in cmdevs:
            name = _child_text(item, "Name")
            if not name:
                continue
            ip = ""
            for ipa in (e for e in item.iter() if _local(e.tag) == "IPAddress"):
                for sub in ipa.iter():
                    if _local(sub.tag) == "IP" and (sub.text or "").strip():
                        ip = sub.text.strip()
                        break
                if ip:
                    break
            if not ip:
                ip = _child_text(item, "IpAddress")  # very old RisPort
            devices.append({"name": name, "ip": ip, "dn": _child_text(item, "DirNumber").split("-")[0],
                            "desc": _child_text(item, "Description"), "status": _child_text(item, "Status"),
                            "httpd": _child_text(item, "Httpd"), "model_id": _child_text(item, "Model")})
    state = next((e.text or "" for e in root.iter() if _local(e.tag) == "StateInfo"), "")
    return devices, state


def _ris_items(names):
    if names is None:
        return ""
    return "".join(f"<soap:item><soap:Item>{html.escape(n)}</soap:Item></soap:item>" for n in names)


def _merge(found, devs):
    for d in devs:
        old = found.get(d["name"])
        if old is None or (d["status"] == "Registered" and old["status"] != "Registered") or \
                (d["ip"] and not old["ip"]):
            found[d["name"]] = d


class _Ris:
    def __init__(self, host, user, password, port, timeout):
        self.url = f"https://{host}:{port}{RIS_PATH}"
        self.s = requests.Session()
        self.s.verify = False
        self.s.auth = (user, password)
        self.timeout = timeout

    def call(self, items, status, state="", maxn=1000):
        body = RIS_BODY.format(state=html.escape(state), maxn=maxn, status=status, items=items)
        hdrs = {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '"selectCmDeviceExt"'}
        try:
            r = self.s.post(self.url, data=body.encode(), headers=hdrs, timeout=self.timeout)
        except requests.RequestException as e:
            raise CucmError(f"Cannot reach {self.url}: {_short_err(e)}")
        if r.status_code == 401:
            raise CucmError("Authentication failed (HTTP 401). The user needs the 'Standard CCM Admin Users' + "
                            "'Standard SERVICEABILITY Read Only' (or AXL/RealtimeAndTraceCollection) roles.")
        if r.status_code not in (200, 500):
            raise CucmError(f"HTTP {r.status_code} from {self.url}: {r.text[:200]}")
        try:
            return parse_ris(r.text)
        except ET.ParseError:
            raise CucmError(f"Non-XML reply from {self.url}: {r.text[:200]}")

    def paged(self, items, status, log, label):
        found, state, maxn = {}, "", 1000
        for page in range(200):
            devs, new_state = self.call(items, status, state, maxn)
            before = len(found)
            _merge(found, devs)
            if log:
                log(f"RisPort {label} page {page + 1}: {len(devs)} entries, {len(found)} phones so far")
            if len(found) == before or not new_state or new_state == state or len(devs) < maxn:
                break
            state = new_state
        return found


def axl_phone_names(host, user, password, port=8443, timeout=60, log=None):
    """All phone device names from CUCM AXL listPhone (schema versions newest first, 5000 per page)."""
    url = f"https://{host}:{port}/axl/"
    s = requests.Session()
    s.verify = False
    s.auth = (user, password)
    last = ""
    for ver in AXL_VERSIONS:
        names, skip, first = [], 0, 5000
        while True:
            body = AXL_LIST_PHONE.format(ver=ver, skip=skip, first=first)
            hdrs = {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"CUCM:DB ver={ver} listPhone"'}
            try:
                r = s.post(url, data=body.encode(), headers=hdrs, timeout=timeout)
            except requests.RequestException as e:
                raise CucmError(f"Cannot reach AXL at {url}: {_short_err(e)}")
            if r.status_code == 401:
                raise CucmError("AXL authentication failed (HTTP 401). This CUCM needs exact device names for "
                                "RisPort, which are read over AXL - give the user the 'Standard AXL API Access' role.")
            if r.status_code == 599:
                last = f"AXL {ver} not supported"
                break
            try:
                root = ET.fromstring(r.text)
            except ET.ParseError:
                raise CucmError(f"AXL HTTP {r.status_code}: non-XML reply: {r.text[:200]}")
            fault = next((e for e in root.iter() if _local(e.tag) == "faultstring"), None)
            if fault is not None:
                if not names and "version" in (fault.text or "").lower():
                    last = f"AXL {ver}: {fault.text}"
                    break
                raise CucmError(f"AXL fault: {fault.text}")
            page = [(c.text or "").strip() for ph in root.iter() if _local(ph.tag) == "phone"
                    for c in ph if _local(c.tag) == "name" and (c.text or "").strip()]
            names.extend(page)
            if log:
                log(f"AXL {ver}: {len(names)} phone names")
            if len(page) < first:
                return names
            skip += first
    raise CucmError(f"No AXL schema version accepted by {host} ({last}).")


def cucm_discover(host, user, password, status="Registered", port=8443, timeout=30, log=None):
    """Ask CUCM RisPort70 for phones. Returns list of device dicts (deduped by name, Registered preferred).

    Newer CUCM releases reject a bare '*' in SelectItems ("SelectItems cannot contain *"), so this falls back
    to an empty selection, then to AXL listPhone names queried 1000 at a time by exact name."""
    ris = _Ris(host, user, password, port, timeout)
    try:
        return list(ris.paged(_ris_items(["*"]), status, log, "wildcard").values())
    except CucmError as e:
        if not str(e).startswith("RisPort fault"):
            raise
        if log:
            log(f"Wildcard rejected ({e}); trying an empty selection...")
    try:
        found = ris.paged(_ris_items(None), status, log, "all")
        if found:
            return list(found.values())
    except CucmError as e:
        if not str(e).startswith("RisPort fault"):
            raise
    if log:
        log("RisPort needs exact names on this CUCM; reading phone names over AXL...")
    names = axl_phone_names(host, user, password, port=port, log=log)
    found, batch = {}, 1000
    nb = (len(names) + batch - 1) // batch
    for i in range(0, len(names), batch):
        chunk = names[i:i + batch]
        devs, _st = ris.call(_ris_items(chunk), status, maxn=2000 if status == "Any" else batch)
        _merge(found, devs)
        if log:
            log(f"RisPort batch {i // batch + 1}/{nb}: {len(found)} phones found")
    return list(found.values())


# ----------------------------------------------------------------------------------------------- export
def export_csv(results, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([h for _k, h, _w in COLUMNS])
        for r in results:
            w.writerow([r.get(k, "") for k, _h, _w in COLUMNS])


def export_xlsx(results, path, title="Cisco IP Phone Inventory"):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Phones"
    navy, thin = "0B2A4A", Side(style="thin", color="D6DDE6")
    ok = sum(1 for r in results if r.get("status") == ST_OK)
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=14, color=navy)
    ws["A2"] = (f"Generated {datetime.now():%Y-%m-%d %H:%M}  ·  {len(results)} targets  ·  {ok} serials read  ·  "
                f"CiscoIPPhoneSerialGrabber")
    ws["A2"].font = Font(italic=True, color="6B7785", size=9)
    hr = 4
    for c, (_k, h, w) in enumerate(COLUMNS, 1):
        cell = ws.cell(row=hr, column=c, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=navy)
        cell.alignment = Alignment(vertical="center")
        ws.column_dimensions[get_column_letter(c)].width = max(10, w // 7)
    fills = {ST_OK: None, ST_PARTIAL: "FFF3DC", ST_NOTPHONE: "F3F6FA", ST_NOWEB: "FDECEA", ST_DOWN: "F3F6FA",
             ST_ERROR: "FDECEA"}
    for i, r in enumerate(results, hr + 1):
        f = fills.get(r.get("status"))
        for c, (k, _h, _w) in enumerate(COLUMNS, 1):
            v = r.get(k, "")
            cell = ws.cell(row=i, column=c, value=v)
            if k in ("serial", "mac", "dn"):
                cell.number_format = "@"
            cell.border = Border(bottom=thin)
            if f:
                cell.fill = PatternFill("solid", fgColor=f)
    ws.freeze_panes = ws.cell(row=hr + 1, column=1)
    ws.auto_filter.ref = f"A{hr}:{get_column_letter(len(COLUMNS))}{hr + max(len(results), 1)}"

    # summary by model
    sm = wb.create_sheet("Summary")
    sm["A1"] = "Phones by model"
    sm["A1"].font = Font(bold=True, size=13, color=navy)
    counts = {}
    for r in results:
        if r.get("status") in (ST_OK, ST_PARTIAL):
            counts[r.get("model") or "(unknown)"] = counts.get(r.get("model") or "(unknown)", 0) + 1
    sm.append([])
    sm.append(["Model", "Qty"])
    for c in sm[3]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=navy)
    for m, n in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
        sm.append([m, n])
    sm.append(["Total", sum(counts.values())])
    sm.cell(row=sm.max_row, column=1).font = Font(bold=True)
    sm.cell(row=sm.max_row, column=2).font = Font(bold=True)
    st = {}
    for r in results:
        st[r.get("status", "")] = st.get(r.get("status", ""), 0) + 1
    sm.append([])
    sm.append(["Status", "Count"])
    for c in sm[sm.max_row]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=navy)
    for k, n in sorted(st.items()):
        sm.append([k, n])
    sm.column_dimensions["A"].width = 28
    sm.column_dimensions["B"].width = 10
    wb.save(path)


# ----------------------------------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description="Grab serial numbers from Cisco IP phones on the network.")
    ap.add_argument("targets", nargs="*", help="IPs, ranges (10.1.1.10-50), subnets (10.1.1.0/24)")
    ap.add_argument("-f", "--file", help="read targets from a .txt/.csv/.xlsx file")
    ap.add_argument("--cucm", help="discover phone IPs from this CUCM publisher/subscriber (RisPort70)")
    ap.add_argument("--user", help="CUCM user")
    ap.add_argument("--password", help="CUCM password (prompted if omitted)")
    ap.add_argument("--any-status", action="store_true", help="include unregistered phones from CUCM")
    ap.add_argument("--phone-user", help="phone web username (only if phone pages need a login)")
    ap.add_argument("--phone-password", help="phone web password")
    ap.add_argument("-w", "--workers", type=int, default=64)
    ap.add_argument("-t", "--timeout", type=float, default=4.0)
    ap.add_argument("--no-https", action="store_true", help="do not try HTTPS")
    ap.add_argument("-o", "--output", help="output .xlsx or .csv (default: print table)")
    a = ap.parse_args(argv)

    text = "\n".join(a.targets)
    if a.file:
        text += "\n" + read_target_file(a.file)
    extra = {}
    if a.cucm:
        if not a.user:
            ap.error("--cucm needs --user")
        pw = a.password or getpass.getpass(f"Password for {a.user}@{a.cucm}: ")
        devs = cucm_discover(a.cucm, a.user, pw, status="Any" if a.any_status else "Registered",
                             log=lambda m: print(m, file=sys.stderr))
        for d in devs:
            if d["ip"]:
                text += "\n" + d["ip"]
                extra[d["ip"]] = {"hostname": d["name"], "dn": d["dn"], "cucm_desc": d["desc"],
                                  "cucm_status": d["status"]}
        print(f"CUCM returned {len(devs)} phones ({len(extra)} with an IP)", file=sys.stderr)
    targets, errs = parse_targets(text)
    for e in errs:
        print("skipped:", e, file=sys.stderr)
    if not targets:
        ap.error("no targets")
    auth = (a.phone_user, a.phone_password or "") if a.phone_user else None

    def prog(r, done, total):
        print(f"\r{done}/{total}  {r['ip']:<16} {r['status']:<12} {r.get('serial', '')}" + " " * 10,
              end="", file=sys.stderr, flush=True)

    res = scan(targets, workers=a.workers, timeout=a.timeout, try_https=not a.no_https, auth=auth,
               on_result=prog, extra=extra)
    print(file=sys.stderr)
    if a.output:
        (export_csv if a.output.lower().endswith(".csv") else export_xlsx)(res, a.output)
        print(f"Saved {a.output}", file=sys.stderr)
    else:
        for r in res:
            if r["status"] in (ST_OK, ST_PARTIAL):
                print(f"{r['ip']:<16} {r.get('model', ''):<14} {r.get('serial', ''):<14} {r.get('mac', ''):<13} "
                      f"{r.get('dn', '')}")
    print(f"{sum(r['status'] == ST_OK for r in res)} serials from {len(res)} targets", file=sys.stderr)


if __name__ == "__main__":
    main()
