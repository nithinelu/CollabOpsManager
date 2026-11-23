"""Arabic text of the Phone Serials tab (from Cisco IP Phone Serial Grabber). Merged into i18n.AR;
where both have the same English key, i18n.AR wins."""

SERIALS_AR = {
    # --- tab and layout
    "Phone Serials": "أرقام تسلسل الهواتف",
    "Serial numbers, MACs and models from the Cisco IP phones on the network":
        "الأرقام التسلسلية وعناوين MAC والطرازات من هواتف Cisco IP على الشبكة",
    "Phones need 'Web Access' enabled in CUCM.": "يجب تفعيل Web Access للهواتف في CUCM.",
    "Clear results": "مسح النتائج",
    "Copy serials": "نسخ الأرقام التسلسلية",
    "Export CSV": "تصدير CSV",
    "Export Excel": "تصدير Excel",

    # --- targets
    "Targets": "الأهداف",
    "IP addresses, ranges or subnets,\nsuch as 10.1.1.10-50 or 10.1.1.0/24":
        "عناوين IP أو نطاقات أو شبكات فرعية،\nمثل 10.1.1.10-50 أو 10.1.1.0/24",
    "Load file…": "تحميل ملف…",
    "{n} addresses": "{n} عنوان",
    "{n} invalid": "{n} غير صالح",
    "Load targets": "تحميل الأهداف",
    "Target lists": "قوائم الأهداف",
    "All files": "كل الملفات",
    "Could not read {path}:\n{err}": "تعذرت قراءة {path}:\n{err}",
    "No IP addresses, ranges or subnets found in that file.":
        "لم يتم العثور على عناوين IP أو نطاقات أو شبكات فرعية في هذا الملف.",

    # --- CUCM discovery
    "Discover from CUCM (optional)": "الاكتشاف من CUCM (اختياري)",
    "Registered phones only": "الهواتف المسجّلة فقط",
    "All phones": "كل الهواتف",
    "Discover phones (RisPort)": "اكتشاف الهواتف عبر RisPort",
    "Uses the AXL user on the Cluster tab.\nAdds each phone's IP to the targets,\n"
    "with its device name, DN and description.":
        "يستخدم مستخدم AXL من تبويب المجموعة.\nيضيف إلى الأهداف عنوان IP لكل هاتف\n"
        "مع اسم الجهاز والرقم والوصف.",
    "Asking {host} for phones…": "جارٍ طلب قائمة الهواتف من {host}…",
    "CUCM discovery failed": "فشل الاكتشاف من CUCM",
    "CUCM returned {n} phones; {k} IP addresses were added to the targets.":
        "أعاد CUCM عدد {n} هاتف، وأضيف {k} عنوان IP إلى الأهداف.",
    "{n} had no IP address, because they are not registered.": "{n} بدون عنوان IP لأنها غير مسجّلة.",
    "{n} have their web server turned off: enable 'Web Access' on those phones.":
        "{n} خادم الويب فيها متوقف: فعّل Web Access على هذه الهواتف.",

    # --- scan
    "Scan": "الفحص",
    "Parallel": "عمليات متوازية",
    "Timeout (s)": "المهلة بالثواني",
    "Also try HTTPS (port 443)": "تجربة HTTPS أيضاً على المنفذ 443",
    "Phone web login, if the pages ask for one:": "دخول صفحة الهاتف، إذا طلبته الصفحات:",
    "Phone web user": "مستخدم صفحة الهاتف",
    "Phone web password": "كلمة مرور صفحة الهاتف",
    "▶  Grab serials": "▶  جمع الأرقام التسلسلية",
    "Idle": "جاهز",
    "Parallel and timeout must be numbers.": "يجب أن تكون العمليات المتوازية والمهلة أرقاماً.",
    "These entries are not valid and will be skipped:\n\n{bad}\n\nContinue with {n} addresses?":
        "هذه الإدخالات غير صالحة وسيتم تجاهلها:\n\n{bad}\n\nهل تريد المتابعة مع {n} عنوان؟",
    "Add some IP addresses, ranges or subnets first.": "أضف عناوين IP أو نطاقات أو شبكات فرعية أولاً.",
    "Scanning {n} addresses…": "جارٍ فحص {n} عنوان…",
    "{done} / {total}  ·  last: {ip}  {status}": "{done} / {total}  ·  الأخير: {ip}  {status}",
    "Finished  ·  {n} serial numbers read": "اكتمل  ·  تمت قراءة {n} رقم تسلسلي",
    "Stopped  ·  {n} serial numbers read": "توقف  ·  تمت قراءة {n} رقم تسلسلي",
    "Stopping, finishing the requests already sent…": "جارٍ الإيقاف وإنهاء الطلبات المرسلة…",
    "Scan failed: {err}": "فشل الفحص: {err}",

    # --- results
    "Results": "النتائج",
    "Filter": "تصفية",
    "Phones only": "الهواتف فقط",
    "{n} serials": "{n} رقم تسلسلي",
    "{n} models": "{n} طراز",
    "IP Address": "عنوان IP",
    "Serial Number": "الرقم التسلسلي",
    "MAC Address": "عنوان MAC",
    "Device Name": "اسم الجهاز",
    "Phone DN": "رقم الهاتف",
    "Firmware": "البرنامج الثابت",
    "HW Rev": "إصدار العتاد",
    "CUCM Description": "وصف CUCM",
    "CUCM Status": "حالة CUCM",
    "Source": "المصدر",
    "Note": "ملاحظة",
    # statuses (the Excel / CSV export keeps them in English)
    "OK": "ناجح",
    "No serial": "بدون رقم تسلسلي",
    "Web closed": "الويب مغلق",
    "Not a phone": "ليس هاتفاً",
    "No response": "لا استجابة",
    "Error": "خطأ",
    # right-click menu
    "Copy selected rows": "نسخ الصفوف المحددة",
    "Copy serial": "نسخ الرقم التسلسلي",
    "Copy MAC": "نسخ عنوان MAC",
    "Open phone web page": "فتح صفحة الهاتف",
    "Re-scan selected": "إعادة فحص المحدد",

    # --- copy, clear, export
    "No serial numbers to copy yet.": "لا توجد أرقام تسلسلية للنسخ بعد.",
    "Copied {n} serials: serial, model, MAC and IP, separated by tabs.":
        "تم نسخ {n} رقم تسلسلي مع الطراز وعنوان MAC وعنوان IP، مفصولة بمسافات جدولة.",
    "Clear all results?": "هل تريد مسح جميع النتائج؟",
    "Nothing to export yet.": "لا يوجد شيء للتصدير بعد.",
    "Export": "تصدير",
    "Cannot write {path}. Is it open in Excel?": "تعذرت الكتابة إلى {path}. هل الملف مفتوح في برنامج Excel؟",
    "Export failed:\n{err}": "فشل التصدير:\n{err}",
    "Exported {n} rows to {file}": "تم تصدير {n} صف إلى {file}",
    "Exported {n} rows.\n\nOpen the file now?": "تم تصدير {n} صف.\n\nهل تريد فتح الملف الآن؟",
}
