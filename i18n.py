"""English / Arabic UI text.

English text is the key: _("Run backup now") returns the Arabic when Arabic is
active, otherwise the English. Placeholders use str.format: _("{n} node(s)", n=3).
Technical terms (CUCM, IM&P, SFTP, DRS, COP, ISO, AXL, CUPI, CLI, IP) stay in
English, as they appear that way on CUCM itself. The activity log and CLI output
stay English: they carry CUCM's own English messages.
"""

LANGUAGES = {"en": "English", "ar": "العربية"}

_lang = "en"


def set_language(code):
    global _lang
    _lang = code if code in LANGUAGES else "en"


def language():
    return _lang


def is_rtl():
    return _lang == "ar"


def en(text, **kw):
    """Always English - for activity-log lines (the log also carries CUCM's English messages)."""
    return text.format(**kw) if kw else text


def _(text, **kw):
    out = AR.get(text, text) if _lang == "ar" else text
    if kw:
        out = out.format(**kw)
    if _lang == "ar" and text in AR:
        # Tk lays every line out left-to-right, so mixed Arabic/Latin lines come out
        # in the wrong order. Wrapping each line in a right-to-left embedding
        # (RLE ... PDF) fixes it; a plain RLM mark does not. The RLM before PDF
        # keeps a trailing ")" or "." after English words on the right side.
        out = "\n".join(f"‫{line}‏‬" for line in out.split("\n"))
    return out


def plain(text):
    """Remove the direction marks _() adds (for file names and Excel)."""
    return text.replace("‫", "").replace("‬", "").replace("‏", "")


AR = {
    # ---- window, status bar, tabs
    "CUCM · IM&P · Unity Connection  —  Backup · Upgrade · COP · Export · built-in SFTP":
        "CUCM · IM&P · Unity Connection  —  نسخ احتياطي · ترقية · COP · تصدير · خادم SFTP مدمج",
    "Ready": "جاهز",
    # the name keeps its left-to-right order inside the Arabic line (LRE ... PDF)
    "© 2026 Nithin Eluvathingal  ·  MIT License": "‪© 2026 Nithin Eluvathingal‬  ·  رخصة MIT",
    "Running: {title} ...": "جارٍ التنفيذ: {title} ...",
    "Running": "قيد التشغيل",
    "{title} failed:": "فشلت العملية: {title}",
    "Stop": "إيقاف",
    "Activity log": "سجل النشاط",
    "CLI output": "مخرجات CLI",
    "SFTP stopped": "SFTP متوقف",
    "No cluster": "لا توجد مجموعة",
    "{n} node(s)": "{n} عقدة",
    "{n} node(s) + {c} CUC": "{n} عقدة + {c} CUC",
    "Please wait for the current operation to finish.": "يرجى الانتظار حتى تنتهي العملية الحالية.",
    "Another operation is still running - wait for it or press Stop.":
        "هناك عملية أخرى قيد التشغيل - انتظر انتهاءها أو اضغط إيقاف.",
    "An operation is running. Close anyway?": "هناك عملية قيد التشغيل. هل تريد الإغلاق على أي حال؟",
    "CUCM is transferring files over SFTP. Close anyway?": "يقوم CUCM بنقل ملفات عبر SFTP. هل تريد الإغلاق على أي حال؟",
    "Cluster": "المجموعة",
    "SFTP Server": "خادم SFTP",
    "Backup (DRS)": "النسخ الاحتياطي (DRS)",
    "Upgrade / COP": "الترقية / COP",
    "Data Export": "تصدير البيانات",
    "CLI Console": "وحدة CLI",

    # ---- task names (shown in the status bar and error titles)
    "Discover cluster": "اكتشاف المجموعة",
    "Versions": "الإصدارات",
    "Health check": "فحص الحالة",
    "Dry run": "تشغيل تجريبي",
    "DRS backup": "نسخ احتياطي DRS",
    "DRS device": "جهاز DRS",
    "Checksum": "المجموع الاختباري",
    "Copy upgrade files": "نسخ ملفات الترقية",
    "Upgrade status": "حالة الترقية",
    "Switch version": "تبديل الإصدار",
    "File export": "تصدير الملفات",
    "Inventory export": "تصدير الجرد",
    "Unity Connection inventory export": "تصدير جرد Unity Connection",

    # ---- cluster tab
    "CUCM cluster": "مجموعة CUCM",
    "Unity Connection cluster (optional)": "مجموعة Unity Connection (اختياري)",
    "Publisher IP / FQDN": "الخادم الرئيسي (IP / FQDN)",
    "OS admin user": "مستخدم مسؤول النظام",
    "OS admin password": "كلمة مرور مسؤول النظام",
    "AXL user": "مستخدم AXL",
    "AXL password": "كلمة مرور AXL",
    "CUPI (app admin) user": "مستخدم CUPI (مسؤول التطبيق)",
    "CUPI password": "كلمة مرور CUPI",
    "AXL is only for the Excel inventory ('Standard AXL API Access').":
        "يُستخدم AXL لجرد Excel فقط، ويتطلب صلاحية Standard AXL API Access",
    "OS admin empty = same as CUCM. CUPI is only for the Excel inventory.":
        "إذا تُرك مسؤول النظام فارغاً يُستخدم حساب CUCM. يُستخدم CUPI لجرد Excel فقط.",
    "Remember passwords (encrypted for this Windows user)": "تذكّر كلمات المرور (مشفّرة لمستخدم Windows هذا)",
    "Connect & discover nodes": "اتصال واكتشاف العقد",
    "Refresh versions": "تحديث الإصدارات",
    "Health check report": "تقرير فحص الحالة",
    "Health check + diagnose test": "فحص الحالة + اختبار التشخيص",
    "Dry run (no changes)": "تشغيل تجريبي (بدون تغييرات)",
    "Open reports folder": "فتح مجلد التقارير",
    "Hostname": "اسم المضيف",
    "IP": "IP",
    "Type": "النوع",
    "Role": "الدور",
    "Status": "الحالة",
    "Active version": "الإصدار النشط",
    "Inactive version": "الإصدار غير النشط",
    "Installed COP files": "ملفات COP المثبتة",
    "Nodes come from 'show network cluster' on each publisher (CUCM + IM&P, Unity Connection). "
    "Each cluster's OS admin is used for its own nodes.\nHealth check (pre/post upgrade) runs version, cluster, "
    "status, NTP, DB replication, services and core-dump checks on the nodes checked on the "
    "Upgrade / COP tab and saves a text report.":
        "تُكتشف العقد عبر الأمر show network cluster على الخادم الرئيسي لكل مجموعة، ويُستخدم مسؤول النظام لكل مجموعة لعقدها.\n"
        "فحص الحالة قبل الترقية وبعدها يفحص الإصدار والحالة و NTP ونسخ قاعدة البيانات والخدمات وملفات core\n"
        "على العقد المحددة في تبويب الترقية / COP، ثم يحفظ تقريراً نصياً.",
    "Enter a CUCM and/or Unity Connection publisher address.": "أدخل عنوان الخادم الرئيسي لـ CUCM و/أو Unity Connection.",
    "Discover the cluster first.": "يرجى اكتشاف المجموعة أولاً.",
    "Enter the {where} OS (platform) administrator user and password on the Cluster tab.":
        "أدخل مستخدم وكلمة مرور مسؤول النظام لـ {where} في تبويب المجموعة.",
    "Enter the {name} publisher address on the Cluster tab.": "أدخل عنوان الخادم الرئيسي لـ {name} في تبويب المجموعة.",
    "CUCM": "CUCM",
    "Unity Connection": "Unity Connection",

    # ---- SFTP tab
    "Built-in SFTP server": "خادم SFTP المدمج",
    "Root folder": "المجلد الجذر",
    "Browse…": "استعراض…",
    "Open": "فتح",
    "IP address CUCM uses to reach this PC": "عنوان IP الذي يستخدمه CUCM للوصول إلى هذا الجهاز",
    "Detect": "اكتشاف",
    "(the address this PC uses to reach the publisher)": "(العنوان الذي يستخدمه هذا الجهاز للوصول إلى الخادم الرئيسي)",
    "Port": "المنفذ",
    "22 is what CUCM expects (DRS on older releases has no port option)":
        "يتوقع CUCM المنفذ 22 (لا يدعم DRS في الإصدارات القديمة تغيير المنفذ)",
    "SFTP user": "مستخدم SFTP",
    "SFTP password": "كلمة مرور SFTP",
    "CUCM stores this in the DRS backup device": "يحفظ CUCM هذه القيمة في جهاز النسخ الاحتياطي DRS",
    "Start the SFTP server when the tool opens (needed for scheduled DRS backups)":
        "تشغيل خادم SFTP عند فتح الأداة (مطلوب لجدولة نسخ DRS الاحتياطية)",
    "Only accept connections from discovered cluster nodes": "قبول الاتصالات من عقد المجموعة المكتشفة فقط",
    "Start SFTP server": "تشغيل خادم SFTP",
    "Allow port in Windows Firewall (admin)": "السماح بالمنفذ في جدار حماية Windows (مسؤول)",
    "Transfers": "عمليات النقل",
    "Time": "الوقت",
    "CUCM node": "عقدة CUCM",
    "File": "الملف",
    "Direction": "الاتجاه",
    "Bytes": "بايت",
    "CUCM → PC": "CUCM ← الجهاز",
    "PC → CUCM": "الجهاز ← CUCM",
    "Folders under the root: backup\\ (DRS backups land here), upgrade\\ (put ISO / COP files here), "
    "export\\ (file get exports).\nCUCM sees the root as '/', e.g. backup directory '/backup', "
    "upgrade directory '/upgrade'.":
        "داخل المجلد الجذر: المجلد backup لنسخ DRS، والمجلد upgrade لملفات ISO و COP، والمجلد export لملفات التصدير.\n"
        "يرى CUCM المجلد الجذر على أنه / ، لذا يكون مجلد النسخ \u200e/backup\u200e ومجلد الترقية \u200e/upgrade\u200e عنده.",
    "Running - CUCM connects to {ip} as {user}": "قيد التشغيل - يتصل CUCM بـ {ip} باسم {user}",
    "Stopped": "متوقف",
    "Enter the publisher on the Cluster tab first (and check it resolves).":
        "أدخل الخادم الرئيسي في تبويب المجموعة أولاً (وتأكد من إمكانية الوصول إليه).",
    "Set an SFTP user and a password of at least 6 characters.": "حدد مستخدم SFTP وكلمة مرور لا تقل عن 6 أحرف.",
    "Set the 'IP address CUCM uses to reach this PC' on the SFTP Server tab.":
        "حدد 'عنوان IP الذي يستخدمه CUCM للوصول إلى هذا الجهاز' في تبويب خادم SFTP.",
    "SFTP IP {ip} is not an address of this PC - fix it on the SFTP Server tab.":
        "عنوان SFTP ‏{ip} ليس من عناوين هذا الجهاز - صحّحه في تبويب خادم SFTP.",
    "The built-in SFTP server is not running (SFTP Server tab).": "خادم SFTP المدمج لا يعمل (تبويب خادم SFTP).",

    # ---- backup tab
    "DRS backup to the built-in SFTP server (runs on the cluster's publisher)":
        "نسخ احتياطي DRS إلى خادم SFTP المدمج (يعمل على الخادم الرئيسي للمجموعة)",
    "CUCM / IM&P": "CUCM / IM&P",
    "Backup device name": "اسم جهاز النسخ الاحتياطي",
    "Directory on SFTP": "المجلد على SFTP",
    "/backup = <root>\\backup (use a separate folder per cluster)":
        "‏/backup = <root>\\backup (استخدم مجلداً منفصلاً لكل مجموعة)",
    "Backups to keep": "عدد النسخ المحفوظة",
    "DRS deletes older backups beyond this": "يحذف DRS النسخ الأقدم بعد هذا العدد",
    "Features": "الميزات",
    "CUCM: UCM,CDR_CAR (PLM on old releases)  |  Unity Connection: CUC":
        "CUCM: ‏UCM,CDR_CAR ‏(PLM في الإصدارات القديمة)  |  Unity Connection: ‏CUC",
    "Run backup now": "تشغيل النسخ الاحتياطي الآن",
    "Create / update backup device": "إنشاء / تحديث جهاز النسخ الاحتياطي",
    "History": "السجل",
    "Device list": "قائمة الأجهزة",
    "Schedules": "الجداول الزمنية",
    "Registered features": "الميزات المسجلة",
    "Cancel running backup": "إلغاء النسخ الجاري",
    "Feature": "الميزة",
    "Server": "الخادم",
    "Component": "المكوّن",
    "Result": "النتيجة",
    "Backups on this PC": "النسخ الاحتياطية على هذا الجهاز",
    "Refresh": "تحديث",
    "Open folder": "فتح المجلد",
    "Size": "الحجم",
    "Modified": "تاريخ التعديل",
    "DRS backup finished: {status}\nTar file: {tar}": "انتهى النسخ الاحتياطي DRS: ‏{status}\nملف Tar: ‏{tar}",
    "Cancel the DRS backup running on the Unity Connection publisher?":
        "إلغاء النسخ الاحتياطي DRS الجاري على الخادم الرئيسي لـ Unity Connection؟",
    "Cancel the DRS backup running on the CUCM publisher?": "إلغاء النسخ الاحتياطي DRS الجاري على الخادم الرئيسي لـ CUCM؟",

    # ---- upgrade / COP tab
    "Files in <root>\\upgrade (CUCM directory /upgrade)": "ملفات ISO و COP في المجلد upgrade",
    "ISO / COP file": "ملف ISO / COP",
    "Add files…": "إضافة ملفات…",
    "Checksum (SHA-512 / MD5)": "المجموع الاختباري SHA-512 / MD5",
    "Options": "الخيارات",
    "Switch version automatically after\na successful upgrade (node reboots)":
        "تبديل الإصدار تلقائياً بعد\nنجاح الترقية (تُعاد تشغيل العقدة)",
    "Run on the checked nodes:": "التشغيل على العقد المحددة:",
    "One after another (publisher first)": "واحدة تلو الأخرى (الخادم الرئيسي أولاً)",
    "All at the same time": "جميعها في نفس الوقت",
    "COP files: usually all nodes, parallel is fine.\nUpgrades: publisher first, then subscribers. "
    "Leave auto-switch off and use Switch version in the maintenance window "
    "(publisher first, wait for it to come up, then subscribers).":
        "ملفات COP: عادةً على جميع العقد، والتشغيل المتوازي مناسب.\nالترقيات: الخادم الرئيسي أولاً ثم الخوادم الفرعية. "
        "اترك التبديل التلقائي متوقفاً واستخدم تبديل الإصدار في نافذة الصيانة "
        "(الخادم الرئيسي أولاً، انتظر حتى يعمل، ثم الخوادم الفرعية).",
    "Target nodes (click to check / uncheck, click ✓ header for all)":
        "العقد المستهدفة - انقر على العقدة لتحديدها، أو على عنوان العمود الأول لتحديد الكل",
    "Install selected file on checked nodes": "تثبيت الملف المحدد على العقد المحددة",
    "Show versions": "عرض الإصدارات",
    "Switch version on checked nodes…": "تبديل الإصدار على العقد المحددة…",
    "Select CUCM upgrade ISO / COP files": "اختر ملفات ترقية CUCM بصيغة ISO / COP",
    "CUCM upgrade / COP": "ترقية CUCM / COP",
    "All files": "جميع الملفات",
    "Select an ISO / COP file in the list first.": "اختر ملف ISO / COP من القائمة أولاً.",
    "Check at least one target node.": "حدد عقدة مستهدفة واحدة على الأقل.",
    "Check at least one node.": "حدد عقدة واحدة على الأقل.",
    "Check the nodes to switch.": "حدد العقد المراد تبديل إصدارها.",
    "COP file": "ملف COP",
    "UPGRADE": "ترقية",
    "Install {kind}": "تثبيت {kind}",
    "on {n} node(s):": "على {n} عقدة:",
    "The nodes will REBOOT into the new version when done.": "ستُعاد تشغيل العقد على الإصدار الجديد عند الانتهاء.",
    "The new version goes to the inactive partition (no reboot).": "يُثبّت الإصدار الجديد على القسم غير النشط (بدون إعادة تشغيل).",
    "Switch version and REBOOT on:": "تبديل الإصدار وإعادة التشغيل على:",
    "This interrupts call processing on these nodes. Continue?": "سيؤدي ذلك إلى توقف معالجة المكالمات على هذه العقد. هل تريد المتابعة؟",
    "connecting…": "جارٍ الاتصال…",
    "installing {name} …": "جارٍ تثبيت {name} …",
    "installation result not confirmed - see CLI output tab": "لم يتم تأكيد نتيجة التثبيت - راجع تبويب مخرجات CLI",
    "{title}: done": "{title}: تم",

    # ---- data export tab
    "Files from the nodes ('file get' to the built-in SFTP server)": "ملفات من العقد ('file get' إلى خادم SFTP المدمج)",
    "What": "المحتوى",
    "Location": "الموقع",
    "File spec": "مواصفات الملف",
    "e.g.": "مثال:",
    "Export files from checked nodes": "تصدير الملفات من العقد المحددة",
    "Open export folder": "فتح مجلد التصدير",
    "Configuration inventory to Excel (publisher)": "جرد الإعدادات إلى Excel (الخادم الرئيسي)",
    "CUCM (AXL SQL)": "CUCM ‏(AXL SQL)",
    "Unity Connection (CUPI REST)": "Unity Connection ‏(CUPI REST)",
    "Custom SQL (optional, added as sheet 'Custom'):": "استعلام SQL مخصص (اختياري، يُضاف كورقة 'Custom'):",
    "Custom CUPI path (optional, e.g. /vmrest/users?query=(alias%20startswith%20a)):":
        "مسار CUPI مخصص (اختياري، مثال: /vmrest/users?query=(alias%20startswith%20a)):",
    "Export inventory to Excel…": "تصدير الجرد إلى Excel…",
    "Check the node(s) to export from.": "حدد العقد المراد التصدير منها.",
    "Enter a location and a file spec.": "أدخل الموقع ومواصفات الملف.",
    "exporting…": "جارٍ التصدير…",
    "{n} file(s)": "{n} ملف",
    "Select at least one inventory item.": "اختر عنصر جرد واحداً على الأقل.",
    "Enter the AXL application user and password on the Cluster tab.": "أدخل مستخدم وكلمة مرور تطبيق AXL في تبويب المجموعة.",
    "Enter the Unity Connection CUPI user and password on the Cluster tab.":
        "أدخل مستخدم وكلمة مرور CUPI لـ Unity Connection في تبويب المجموعة.",
    "Enter the Unity Connection CUPI (application administrator) user and password on the Cluster tab.":
        "أدخل مستخدم وكلمة مرور CUPI (مسؤول التطبيق) لـ Unity Connection في تبويب المجموعة.",

    # ---- CLI console tab
    "Node": "العقدة",
    "Connect": "اتصال",
    "Disconnect": "قطع الاتصال",
    "not connected": "غير متصل",
    "connecting to {host}…": "جارٍ الاتصال بـ {host}…",
    "connected to {host}": "متصل بـ {host}",
    "failed: {err}": "فشل: {err}",
    "Quick command": "أمر سريع",
    "Run": "تشغيل",
    "('show cuc …' commands are for Unity Connection nodes)": "أوامر show cuc مخصصة لعقد Unity Connection فقط",
    "Send": "إرسال",
    "Send password (masked)": "إرسال كلمة المرور (مخفية)",
    "Ctrl-C": "Ctrl-C",
    "Live CLI session - answer any interactive question here (type the answer and press Enter).":
        "جلسة CLI مباشرة - أجب عن أي سؤال تفاعلي هنا (اكتب الإجابة واضغط Enter).",
    "Pick or type a node address.": "اختر أو اكتب عنوان العقدة.",
    "Connect the console first.": "قم بتوصيل وحدة CLI أولاً.",
    "Password to send:": "كلمة المرور المراد إرسالها:",

    # ---- MACD tab (connection bar; the screens' text comes from i18n_macd)
    "MACD": "MACD",
    "Connect to CUCM first (Connect, at the top of the MACD tab).":
        "يرجى الاتصال بـ CUCM أولاً (زر اتصال أعلى تبويب MACD).",
    "Enter the CUCM publisher, AXL user and AXL password on the Cluster tab.":
        "أدخل الخادم الرئيسي لـ CUCM ومستخدم وكلمة مرور AXL في تبويب المجموعة.",
    "Uses the CUCM publisher and AXL user on the Cluster tab. Every change is logged to "
    "logs\\audit_<month>.csv, and the object is saved to backups\\ before it is changed or deleted.":
        "يستخدم الخادم الرئيسي لـ CUCM ومستخدم AXL من تبويب المجموعة.\n"
        "يُسجَّل كل تغيير في ملف audit داخل المجلد logs، ويُحفظ العنصر في المجلد backups قبل تعديله أو حذفه.",
    "Loaded: {counts}": "تم التحميل: {counts}",
}

from i18n_macd import MACD_AR  # noqa: E402 - the MACD tab's text

for _k, _v in MACD_AR.items():
    AR.setdefault(_k, _v)
