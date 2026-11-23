"""Phone background images: resize pictures for each Cisco phone model, write the model's List.xml,
save the files locally (folder or ZIP) and upload them to the CUCM TFTP servers.

Sizes and folders (Cisco admin guides):
  79xx   Desktops/<width>x<height>x<depth>, full image + 'TN-' thumbnail, plain List.xml, up to 50 images
         7941/7942/7961/7962 are 4-bit greyscale (320x196x4)
  8800   Desktops/800x480x24, 800x480 + 139x109 thumbnail, plain List.xml, up to 50 images
  PhoneOS phones (Desk Phone 98XX and the 8875; not Enterprise firmware, so a different List.xml):
         wallpaper-<name>.png + thumbnail-<name>.png, List.xml <ImageItem Name Image Thumbnail Theme> with a
         version that must go up on every change (Configure 9800 and 8875 phones on Unified CM, help.webex.com)
         98XX   Desktops/DP-98xx; 9851: 10 images of 250 KB, 9861 / 9871: 20 images of 1 MB
         8875   Desktops/1024x600x24 (Cisco Community / Cisco Live), 1024x600 + 180x100, 20 images of 1 MB
Phones read new files only after Cisco TFTP is restarted on the TFTP nodes.

Upload goes through the OS Administration pages (Software Upgrades > TFTP File Management), the
same form a browser uses: /cmplatform/j_security_check, then /cmplatform/tftpFileUpload.do with
its Struts token. There is no CLI or API command for it.
"""

import io
import os
import re
import time
import zipfile
from xml.sax.saxutils import quoteattr

try:
    from PIL import Image, ImageOps
except ImportError:          # an older install without Pillow: the rest of the app still starts
    Image = ImageOps = None

# key, series, label, folder, full size, thumbnail size, colour, style, max images, max bytes per image
MODELS = [
    ("7941", "79XX", "7941 · 7942 · 7961 · 7962", "320x196x4", (320, 196), (80, 49), "grey4", "classic", 50, None),
    ("7945", "79XX", "7945 · 7965", "320x212x16", (320, 212), (80, 53), "rgb", "classic", 50, None),
    ("7970", "79XX", "7970 · 7971", "320x212x12", (320, 212), (80, 53), "rgb", "classic", 50, None),
    ("7975", "79XX", "7975", "320x216x16", (320, 216), (80, 54), "rgb", "classic", 50, None),
    ("8800", "88XX", "8841 · 8845 · 8851 · 8861 · 8865", "800x480x24", (800, 480), (139, 109), "rgb",
     "classic", 50, None),
    ("8875", "PhoneOS", "8875", "1024x600x24", (1024, 600), (180, 100), "rgb", "phoneos", 20, 1024 * 1024),
    ("9851", "PhoneOS", "9851", "DP-9851", (480, 240), (100, 56), "rgb", "phoneos", 10, 250 * 1024),
    ("9861", "PhoneOS", "9861", "DP-9861", (800, 480), (150, 90), "rgb", "phoneos", 20, 1024 * 1024),
    ("9861NR", "PhoneOS", "9861 NR", "DP-9861NR", (800, 480), (150, 90), "rgb", "phoneos", 20, 1024 * 1024),
    ("9871", "PhoneOS", "9871", "DP-9871", (1280, 720), (228, 128), "rgb", "phoneos", 20, 1024 * 1024),
    ("9871NR", "PhoneOS", "9871 NR", "DP-9871NR", (1280, 720), (228, 128), "rgb", "phoneos", 20, 1024 * 1024),
]
SERIES = ("79XX", "88XX", "PhoneOS")
BY_KEY = {m[0]: m for m in MODELS}
PICTURE_TYPES = "*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp"


class BackgroundError(Exception):
    pass


# PhoneOS logo sizes (Configure 9800 and 8875 phones on Unified CM); 79XX / 88XX phones have no logo
LOGO_SIZE = {"8875": (380, 250), "9851": (190, 125), "9861": (380, 250), "9861NR": (380, 250),
             "9871": (494, 325), "9871NR": (494, 325)}


def model(key):
    k, series, label, folder, full, thumb, colour, style, max_n, max_bytes = BY_KEY[key]
    return {"key": k, "series": series, "label": label, "folder": folder, "dir": "Desktops/" + folder,
            "full": full, "thumb": thumb, "colour": colour, "style": style, "max": max_n, "max_bytes": max_bytes,
            "logo": LOGO_SIZE.get(k)}


NAME_MAX = 24          # typed names; names taken from the picture's file name stop at 16


def clean_name(text, taken=(), max_len=NAME_MAX, typed=False):
    """Picture name used in the file names: letters and digits only (PhoneOS phones accept nothing else).
    typed: a name the user typed - only a picture extension at the end is dropped, not every '.xxx'."""
    text = re.sub(r"\.(png|jpe?g|bmp|gif|tiff?|webp)$", "", text.strip(), flags=re.I) if typed else \
        os.path.splitext(os.path.basename(text))[0]
    base = re.sub(r"[^A-Za-z0-9]", "", text)[:max_len] or "picture"
    name, n = base, 2
    while name.lower() in {t.lower() for t in taken}:
        name, n = f"{base}{n}", n + 1
    return name


def file_names(m, name):
    """(full image, thumbnail) file names for a model."""
    if m["style"] == "phoneos":
        return f"wallpaper-{name}.png", f"thumbnail-{name}.png"
    return f"{name}.png", f"TN-{name}.png"


def _open(path):
    if Image is None:
        raise BackgroundError("The Pillow package is missing. Run setup.bat again (it installs requirements.txt).")
    try:
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)        # phone photos keep their rotation in EXIF
        img.load()
    except (OSError, ValueError) as e:
        raise BackgroundError(f"Cannot open {os.path.basename(path)}: {e}") from e
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        flat = Image.new("RGB", img.size, (0, 0, 0))   # transparent parts become black
        flat.paste(img, mask=img.split()[-1])
        return flat
    return img.convert("RGB")


def resize(img, size, fit="fill"):
    """fill: cover the whole screen and cut off what sticks out; fit: whole picture, black bars."""
    if fit == "fit":
        out = Image.new("RGB", size, (0, 0, 0))
        small = ImageOps.contain(img, size, Image.LANCZOS)
        out.paste(small, ((size[0] - small.width) // 2, (size[1] - small.height) // 2))
        return out
    return ImageOps.fit(img, size, Image.LANCZOS, centering=(0.5, 0.5))


def _png(img, colour, max_bytes=None):
    buf = io.BytesIO()
    if colour == "grey4":
        grey = img.convert("L").point(lambda v: (v // 17) * 17)            # 16 grey levels
        pal = grey.convert("P", palette=Image.ADAPTIVE, colors=16)
        pal.save(buf, "PNG", optimize=True, bits=4)
    else:
        img.save(buf, "PNG", optimize=True)
        if max_bytes and buf.tell() > max_bytes:          # too big for the 9800 limit: 256 colours
            buf = io.BytesIO()
            img.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG) \
                .save(buf, "PNG", optimize=True)
    data = buf.getvalue()
    if max_bytes and len(data) > max_bytes:
        raise BackgroundError(f"image is {len(data) // 1024} KB, the phone takes at most {max_bytes // 1024} KB")
    return data


def list_xml(m, items, version="1.0", logo=False):
    """items: [(name, theme)]; logo: list logo.png too (PhoneOS only). Returns List.xml as bytes."""
    lines = ['<CiscoIPPhoneImageList version="%s">' % version if m["style"] == "phoneos" else "<CiscoIPPhoneImageList>"]
    for name, theme in items:
        full, thumb = file_names(m, name)
        img, tn = f"TFTP:{m['dir']}/{full}", f"TFTP:{m['dir']}/{thumb}"
        if m["style"] == "phoneos":
            lines.append(f"<ImageItem Name={quoteattr(name)} Image={quoteattr(img)} Thumbnail={quoteattr(tn)} "
                         f"Theme={quoteattr(theme if theme in ('light', 'dark') else 'light')}/>")
        else:
            lines.append(f"<ImageItem Image={quoteattr(tn)} URL={quoteattr(img)}/>")
    if logo and m["style"] == "phoneos":            # Cisco: the logo entry must be named exactly "logo"
        lines.append(f'<ImageItem Name="logo" Image={quoteattr("TFTP:" + m["dir"] + "/" + LOGO_FILE)}/>')
    lines.append("</CiscoIPPhoneImageList>")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def _version_after(ours, theirs):
    """PhoneOS phones fetch List.xml again only when its version goes up: above the server's own."""
    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    v = max(num(ours), int(num(theirs)) + 1 if theirs is not None else 0)
    return f"{int(v)}.0" if v == int(v) else f"{v:g}"


def merge_list(m, existing, ours):
    """Keep what the List.xml already on the TFTP server lists (Cisco's default PhoneOS wallpapers say
    'Please Add Images to the end of the list'), drop entries these pictures replace, add ours at the end.
    Returns (List.xml bytes, entries kept from the server)."""
    from xml.etree import ElementTree as ET

    def parse(data):
        return ET.fromstring(data, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
    new = parse(ours)
    try:
        old = parse(existing)
    except ET.ParseError as e:
        raise BackgroundError(f"the List.xml now on the server is not valid XML ({e})") from e
    phoneos = m["style"] == "phoneos"
    key = "Image" if phoneos else "URL"
    replaced = {it.get(key) for it in new}
    names = {it.get("Name") for it in new} if phoneos else set()

    def line(node):
        if node.tag is ET.Comment:
            return f"<!--{node.text}-->"
        return f"<{node.tag} " + " ".join(f"{k}={quoteattr(v)}" for k, v in node.attrib.items()) + "/>"
    kept, lines = 0, []
    for node in old:
        if node.tag == "ImageItem":
            if node.get(key) in replaced or (node.get("Name") and node.get("Name") in names):
                continue
            kept += 1
        lines.append(line(node))
    lines += [line(node) for node in new]
    head = (f'<CiscoIPPhoneImageList version="{_version_after(new.get("version"), old.get("version"))}">'
            if phoneos else "<CiscoIPPhoneImageList>")
    return ("\r\n".join([head] + lines + ["</CiscoIPPhoneImageList>"]) + "\r\n").encode("utf-8"), kept


LOGO_FILE = "logo.png"


def logo_png(path, m):
    """The logo for a PhoneOS model: scaled in proportion to fit the model's logo size, transparency kept."""
    if Image is None:
        raise BackgroundError("The Pillow package is missing. Run setup.bat again (it installs requirements.txt).")
    try:
        img = ImageOps.exif_transpose(Image.open(path))
        img.load()
    except (OSError, ValueError) as e:
        raise BackgroundError(f"Cannot open the logo {os.path.basename(path)}: {e}") from e
    img = ImageOps.contain(img.convert("RGBA"), m["logo"], Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    if m["max_bytes"] and buf.tell() > m["max_bytes"]:
        raise BackgroundError(f"the logo is {buf.tell() // 1024} KB, the phone takes at most {m['max_bytes'] // 1024} KB")
    return buf.getvalue()


def build(pictures, model_keys, fit="fill", version="1.0", log=None, logo=None):
    """pictures: [{"path", "name", "theme"}]; logo: a picture file for the PhoneOS phones' logo, or None.
    Returns {folder dir: [(file name, bytes)]} with List.xml last."""
    if not pictures and not logo:
        raise BackgroundError("Add at least one picture.")
    if not model_keys:
        raise BackgroundError("Tick at least one phone model.")
    names = [p["name"] for p in pictures]
    if len({n.lower() for n in names}) != len(names):
        raise BackgroundError("Two pictures have the same name.")
    opened = {p["path"]: _open(p["path"]) for p in pictures}
    out = {}
    for key in model_keys:
        m = model(key)
        with_logo = bool(logo) and m["style"] == "phoneos"
        if not pictures and not with_logo:
            raise BackgroundError(f"{m['label']} phones have no logo: add at least one picture for them.")
        if len(pictures) > m["max"]:
            raise BackgroundError(f"{m['label']} phones show at most {m['max']} pictures; {len(pictures)} are added.")
        files = []
        for p in pictures:
            full, thumb = file_names(m, p["name"])
            img = opened[p["path"]]
            try:
                files.append((full, _png(resize(img, m["full"], fit), m["colour"], m["max_bytes"])))
                files.append((thumb, _png(resize(img, m["thumb"], fit), m["colour"])))
            except BackgroundError as e:
                raise BackgroundError(f"{p['name']} for {m['label']}: {e}") from e
        if with_logo:
            try:
                files.append((LOGO_FILE, logo_png(logo, m)))
            except BackgroundError as e:
                raise BackgroundError(f"logo for {m['label']}: {e}") from e
        files.append(("List.xml", list_xml(m, [(p["name"], p.get("theme", "light")) for p in pictures], version,
                                           logo=with_logo)))
        out[m["dir"]] = files
        if log:
            log(f"{m['dir']}: {len(pictures)} picture(s) at {m['full'][0]}x{m['full'][1]}, "
                f"thumbnails {m['thumb'][0]}x{m['thumb'][1]}")
    return out


def save_folder(built, root):
    """Write the files under root\\Desktops\\<folder>\\ (the layout of the TFTP server)."""
    n = 0
    for d, files in built.items():
        target = os.path.join(root, *d.split("/"))
        os.makedirs(target, exist_ok=True)
        for name, data in files:
            with open(os.path.join(target, name), "wb") as f:
                f.write(data)
            n += 1
    return n


def save_zip(built, path):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for d, files in built.items():
            for name, data in files:
                z.writestr(f"{d}/{name}", data)
    return sum(len(f) for f in built.values())


# ---------------------------------------------------------------- upload to CUCM TFTP
_TOKEN = re.compile(r'<input[^>]*name=["\']token["\'][^>]*>', re.I)
_VALUE = re.compile(r'value=["\']([^"\']*)["\']', re.I)
_OK = re.compile(r"uploaded\s+successfully|successfully\s+uploaded", re.I)
_ERR = re.compile(r'class=["\'][^"\']*(?:error|failure)[^"\']*["\'][^>]*>\s*(?:<[^>]+>\s*)*([^<]{3,200})', re.I)


def _token(html):
    m = _TOKEN.search(html or "")
    if not m:
        return None
    v = _VALUE.search(m.group(0))
    return v.group(1) if v else None


class TftpUploader:
    """One OS Administration web session on one CUCM node."""

    def __init__(self, host, user, password, timeout=60, session=None):
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.host, self.user, self.password, self.timeout = host, user, password, timeout
        self.base = f"https://{host}/cmplatform"
        self.s = session or requests.Session()
        self.s.verify = False
        self.token = None

    def login(self):
        self.s.get(self.base + "/", timeout=self.timeout)
        self.s.post(self.base + "/j_security_check", timeout=self.timeout,
                    data={"appNav": "cmplatform", "j_username": self.user, "j_password": self.password})
        page = self.s.get(self.base + "/tftpFileUpload.do", timeout=self.timeout)
        self.token = _token(page.text)
        if not self.token:
            if "j_password" in page.text or "j_security_check" in page.text:
                raise BackgroundError(f"{self.host}: OS Administration login refused - check the OS admin user "
                                      "and password on the Cluster tab.")
            raise BackgroundError(f"{self.host}: the TFTP upload page did not open (HTTP {page.status_code}).")

    def upload(self, directory, name, data):
        if not self.token:
            self.login()
        r = self.s.post(self.base + "/tftpFileUpload.do", timeout=self.timeout, files={
            "struts.token.name": (None, "token"), "token": (None, self.token),
            "file": (name, data, "application/octet-stream"), "directory": (None, directory)})
        self.token = _token(r.text)
        if _OK.search(r.text):
            return True
        err = _ERR.search(r.text)
        if r.status_code != 200 or err:
            raise BackgroundError(f"{self.host}: {directory}/{name} not uploaded: " +
                                  (err.group(1).strip() if err else f"HTTP {r.status_code}"))
        raise BackgroundError(f"{self.host}: {directory}/{name}: CUCM did not confirm the upload.")

    def upload_all(self, built, log=None, cancel=None, progress=None):
        self.login()
        total = sum(len(f) for f in built.values())
        done = 0
        for d, files in built.items():
            for name, data in files:
                if cancel is not None and cancel.is_set():
                    raise BackgroundError("Stopped.")
                self.upload(d, name, data)
                done += 1
                if progress:
                    progress(done, total)
            if log:
                log(f"[{self.host}] uploaded {len(files)} file(s) to {d}")
        return done


TFTP_SERVICE = "Cisco Tftp"
CONTROL_CENTER = "https://{host}:8443/controlcenterservice2/services/ControlCenterServices"
_SOAP = ('<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
         'xmlns:soap="http://schemas.cisco.com/ast/soap"><soapenv:Header/><soapenv:Body>{body}'
         '</soapenv:Body></soapenv:Envelope>')
# CUCM's Axis2 checks the order strictly: NodeName, then ControlType, then ServiceList ("Unexpected subelement
# ControlType" from CUCM 12.5 when NodeName was left out). NodeName = the server's name under System > Server.
_RESTART_BODY = ("<soap:soapDoControlServices><soap:ControlServiceRequest><soap:NodeName>{node}</soap:NodeName>"
                 "<soap:ControlType>Restart</soap:ControlType>"
                 "<soap:ServiceList><soap:item>{name}</soap:item></soap:ServiceList></soap:ControlServiceRequest>"
                 "</soap:soapDoControlServices>")
_STATUS_BODIES = (       # tried in turn until the node accepts one: just TFTP, every service, no list at all
    "<soap:soapGetServiceStatus><soap:ServiceStatus><soap:item>{name}</soap:item></soap:ServiceStatus>"
    "</soap:soapGetServiceStatus>",
    "<soap:soapGetServiceStatus><soap:ServiceStatus></soap:ServiceStatus></soap:soapGetServiceStatus>",
    "<soap:soapGetServiceStatus/>")
_http_post = None              # tests put a fake here; None = requests.post


class TftpNotActive(BackgroundError):
    """Cisco TFTP is not activated on the node: it is not a TFTP server, so there is nothing to restart."""


def _service_items(xml_text):
    """[(ServiceName, ServiceStatus, ReasonCodeString)] from a Control Center reply, whatever its prefixes."""
    out = []
    for item in re.findall(r"<(?:\w+:)?item\b[^>]*>(.*?)</(?:\w+:)?item>", xml_text, re.S):
        def field(tag):
            m = re.search(rf"<(?:\w+:)?{tag}\b[^>]*>(.*?)</(?:\w+:)?{tag}>", item, re.S)
            return m.group(1).strip() if m else ""
        if field("ServiceName"):
            out.append((field("ServiceName"), field("ServiceStatus"), field("ReasonCodeString")))
    return out


def _control_center(host, user, password, action, body, timeout=60):
    import requests
    post = _http_post or requests.post
    try:
        r = post(CONTROL_CENTER.format(host=host), data=_SOAP.format(body=body).encode("utf-8"),
                 headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"{action}"'},
                 auth=(user, password), verify=False, timeout=timeout)
    except Exception as e:
        raise BackgroundError(f"{host}: cannot reach the Serviceability API (port 8443): {e}") from e
    if r.status_code in (401, 403):
        raise BackgroundError(f"{host}: the AXL user on the Cluster tab may not use the Serviceability API "
                              f"(HTTP {r.status_code}). Give it a role with Serviceability access, or restart "
                              "Cisco TFTP in Cisco Unified Serviceability.")
    fault = re.search(r"<(?:\w+:)?faultstring>(.*?)</(?:\w+:)?faultstring>", r.text, re.S)
    if r.status_code != 200 or fault:
        err = BackgroundError(f"{host}: the Serviceability API refused {action}: " +
                              (fault.group(1).strip()[:200] if fault else f"HTTP {r.status_code}"))
        err.output = r.text[:4000]
        raise err
    return r.text


def _tftp_state(reply):
    return {n.lower(): (st, why) for n, st, why in _service_items(reply)}.get(TFTP_SERVICE.lower())


def restart_tftp(host, user, password, node_names=(), cancel=None, wait=180, poll=5, log=None):
    """Restart Cisco TFTP on one node the way Serviceability's Control Center does (the CLI cannot:
    'utils service restart' only takes network services), then wait until the node reports it Started.
    Uses an application user with Serviceability access - the AXL user - not the OS admin.
    node_names: what CUCM may call this server (hostname, IP); each is tried until CUCM accepts one."""
    from xml.sax.saxutils import escape
    if not user or not password:
        raise BackgroundError("Enter the AXL user and password on the Cluster tab: CUCM restarts Cisco TFTP "
                              "through its Serviceability API, which takes that user, not the OS admin.")
    names = list(dict.fromkeys(n for n in list(node_names) + [host] if n))
    state = reply = None
    errors = []                                        # (server name tried, error) - the first is the likeliest name
    for name in names:
        try:
            reply = _control_center(host, user, password, "soapDoControlServices",
                                    _RESTART_BODY.format(node=escape(name), name=TFTP_SERVICE))
        except BackgroundError as e:
            if "may not use the Serviceability API" in str(e):
                raise
            errors.append((name, e))                   # e.g. CUCM knows this server by its other name
            continue
        state = _tftp_state(reply)
        if state:
            if log:
                log(f"[{host}] Serviceability API took the restart for server name '{name}'")
            break
        e = BackgroundError(f"{host}: the Serviceability API did not restart Cisco Tftp for server name '{name}'")
        e.output = reply[:4000]
        errors.append((name, e))
    if not state:
        first = errors[0][1]                           # what CUCM said for the likeliest name; all replies go to .output
        first.output = "\n".join(f"server name '{n}': {e}\n{getattr(e, 'output', '')}".rstrip() for n, e in errors)
        raise first
    if re.search(r"not\s*activ|deactiv", " ".join(state), re.I):
        raise TftpNotActive(f"{host}: Cisco Tftp is not activated on this node ({' - '.join(x for x in state if x)})")
    end = time.time() + wait
    while True:
        if state and state[0].lower() == "started":
            if log:
                log(f"[{host}] Cisco Tftp restarted (Serviceability API reports Started)")
            return reply
        if (cancel is not None and cancel.is_set()) or time.time() > end:
            err = BackgroundError(f"{host}: Cisco Tftp did not report Started within {wait} s after the restart" +
                                  (f" (last status: {' - '.join(x for x in state if x)})" if state else ""))
            err.output = reply[:4000]
            raise err
        time.sleep(poll)
        bodies = list(_STATUS_BODIES)
        while True:
            try:
                reply = _control_center(host, user, password, "soapGetServiceStatus",
                                        bodies[0].format(name=TFTP_SERVICE))
                break
            except BackgroundError as e:
                if len(bodies) == 1 or "may not use the Serviceability API" in str(e):
                    raise
                bodies.pop(0)                          # this CUCM wants the request shaped differently
        state = _tftp_state(reply) or state


def fetch(host, directory, name, timeout=8, http_get=None):
    """The file as the node's TFTP server hands it to phones (HTTP port 6970), or None when it has none."""
    import requests
    get = http_get or requests.get
    try:
        r = get(f"http://{host}:6970/{directory}/{name}", timeout=timeout)
    except Exception as e:
        raise BackgroundError(f"{host}: cannot read {directory}/{name} from TFTP (port 6970): {e}") from e
    return r.content if r.status_code == 200 and r.content.strip() else None


def served(host, directory, name, data, timeout=8, http_get=None):
    """True when the node's TFTP server hands out this exact file (HTTP port 6970, as phones fetch it)."""
    import requests
    get = http_get or requests.get
    try:
        r = get(f"http://{host}:6970/{directory}/{name}", timeout=timeout)
        return r.status_code == 200 and r.content == data
    except Exception:
        return False


def wait_served(host, directory, name, data, secs=90, http_get=None, cancel=None):
    end = time.time() + secs
    while True:
        if served(host, directory, name, data, http_get=http_get):
            return True
        if time.time() > end or (cancel is not None and cancel.is_set()):
            return False
        time.sleep(5)
