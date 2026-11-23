"""Arabic text of the Phone Backgrounds tab. Merged into i18n.AR; where both have the same English key,
i18n.AR wins."""

BG_AR = {
    # --- tab and layout
    "Phone Backgrounds": "خلفيات الهواتف",
    "Users pick the picture on the phone (Settings › Wallpaper). CUCM must allow it: Common Phone Profile ›\n"
    "Enable End User Access to Phone Background Image Setting, or set Background Image = List.xml for all phones.":
        "يختار المستخدم الصورة من الهاتف عبر الإعدادات ثم الخلفية. يجب أن يسمح CUCM بذلك من Common Phone Profile:\n"
        "فعّل Enable End User Access to Phone Background Image Setting، أو اضبط Background Image على List.xml لكل الهواتف.",
    "⇪  Upload to TFTP servers": "⇪  رفع إلى خوادم TFTP",
    "Save as ZIP…": "حفظ كملف ZIP…",
    "Save to folder…": "حفظ في مجلد…",
    "TFTP servers (CUCM nodes from the Cluster tab)": "خوادم TFTP، وهي عُقد CUCM من تبويب المجموعة",
    "Upload: OS admin user; TFTP restart: AXL user (Cluster tab).\nUpload to every node that runs Cisco TFTP.":
        "الرفع بمستخدم إدارة النظام، وإعادة تشغيل TFTP بمستخدم AXL من تبويب المجموعة.\n"
        "ارفع الملفات إلى كل عقدة تعمل عليها خدمة Cisco TFTP.",
    "Restarting Cisco TFTP needs the AXL user and password on the Cluster tab (CUCM restarts it through its "
    "Serviceability API, not the OS admin login). Enter them, or untick 'Restart Cisco TFTP after the upload'.":
        "تحتاج إعادة تشغيل Cisco TFTP إلى مستخدم AXL وكلمة مروره في تبويب المجموعة، لأن CUCM يعيد تشغيلها عبر "
        "واجهة Serviceability وليس بدخول إدارة النظام. أدخلهما أو ألغِ تحديد إعادة تشغيل Cisco TFTP بعد الرفع.",

    # --- pictures
    "Pictures": "الصور",
    "Name": "الاسم",
    "File name": "اسم الملف",
    "Rename": "إعادة التسمية",
    "Rename all…": "إعادة تسمية الكل…",
    "Short name for all pictures. They are numbered,\nsuch as Wall1, Wall2 (letters and digits only):":
        "اسم قصير لكل الصور، وتُرقَّم تلقائياً\nمثل Wall1 و Wall2. أحرف إنجليزية وأرقام فقط:",
    "PhoneOS theme": "نمط PhoneOS",
    "Light": "فاتح",
    "Dark": "داكن",
    "Add pictures…": "إضافة صور…",
    "Add pictures": "إضافة صور",
    "Remove": "إزالة",
    "Clear": "مسح",
    "Remove all pictures from the list?": "هل تريد إزالة كل الصور من القائمة؟",

    # --- models and options
    "Phone models": "طرازات الهواتف",
    "Cisco IP Phone 79XX": "هواتف Cisco IP 79XX",
    "Cisco IP Phone 88XX": "هواتف Cisco IP 88XX",
    "PhoneOS: Desk Phone 98XX, 8875": "هواتف PhoneOS: طرازات 98XX و8875",
    "Options": "الخيارات",
    "Picture shape differs from the screen:": "إذا اختلف شكل الصورة عن الشاشة:",
    "Fill the screen (cut the edges)": "ملء الشاشة مع قص الأطراف",
    "Show the whole picture (black bars)": "إظهار الصورة كاملة مع أشرطة سوداء",
    "Restart Cisco TFTP after the upload\n(phones only see new files after it)":
        "إعادة تشغيل Cisco TFTP بعد الرفع\nلا ترى الهواتف الملفات الجديدة إلا بعدها",
    "Each model gets its own folder: full pictures,\nthumbnails and a List.xml that lists them.":
        "لكل طراز مجلد خاص فيه الصور بالحجم الكامل\nوالصور المصغرة وملف List.xml الذي يسردها.",

    # --- preview
    "Preview": "معاينة",
    "Model": "الطراز",
    "{w}x{h}, thumbnail {tw}x{th}": "{w}x{h}، المصغرة {tw}x{th}",

    # --- checks, save and upload
    "Add at least one picture.": "أضف صورة واحدة على الأقل.",
    "Tick at least one phone model.": "حدد طراز هاتف واحداً على الأقل.",
    "These pictures are not there any more:": "هذه الصور لم تعد موجودة:",
    "{model} phones show at most {n} pictures; {have} are in the list.":
        "تعرض هواتف {model} عدد {n} صورة كحد أقصى، وفي القائمة {have}.",
    "Folder for the phone background files": "مجلد ملفات خلفيات الهواتف",
    "Save the phone background files": "حفظ ملفات خلفيات الهواتف",
    "Cannot write {path}. Is it open in another program?": "تعذرت الكتابة إلى {path}. هل الملف مفتوح في برنامج آخر؟",
    "Saved {n} files to {path}": "تم حفظ {n} ملف في {path}",
    "Save phone backgrounds": "حفظ خلفيات الهواتف",
    "Upload phone backgrounds": "رفع خلفيات الهواتف",
    "Tick at least one TFTP server. Find the nodes with 'Connect & discover nodes' on the Cluster tab.":
        "حدد خادم TFTP واحداً على الأقل. اعثر على العُقد باستخدام Connect & discover nodes في تبويب المجموعة.",
    "Upload {n} pictures to these folders:": "رفع {n} صورة إلى هذه المجلدات:",
    "on:": "على:",
    "Keep what List.xml on the server lists, such as\nCisco's default wallpapers, and add these after it":
        "الإبقاء على ما يسرده List.xml على الخادم\nمثل خلفيات Cisco الافتراضية،\nوإضافة هذه الصور بعدها",
    "Pictures each List.xml already lists stay; these are added after them.":
        "تبقى الصور الموجودة في كل List.xml، وتُضاف هذه الصور بعدها.",
    "PhoneOS logo": "شعار PhoneOS",
    "Logo…": "الشعار…",
    "none": "لا يوجد",
    "Logo for the PhoneOS phones (PNG with a transparent background looks best)":
        "شعار هواتف PhoneOS، والأفضل ملف PNG بخلفية شفافة",
    "and the logo to the PhoneOS folders": "والشعار إلى مجلدات PhoneOS",
    "{model} phones have no logo: add at least one picture for them.":
        "لا تدعم هواتف {model} الشعار، فأضف صورة واحدة على الأقل لها.",
    "uploaded, but Cisco TFTP did not restart":"تم الرفع، لكن لم تُعد خدمة Cisco TFTP التشغيل",
    "uploaded; Cisco TFTP is not activated on this node": "تم الرفع، لكن خدمة Cisco TFTP غير مفعّلة على هذه العقدة",
    "The files are uploaded, but Cisco TFTP did not restart on {n} node(s), so phones keep the old list. "
    "CUCM's reply is in the activity log. Restart Cisco TFTP in Cisco Unified Serviceability › Tools › "
    "Control Center - Feature Services.":
        "تم رفع الملفات، لكن لم تُعد خدمة Cisco TFTP التشغيل على {n} عقدة، لذا تبقى الهواتف على القائمة القديمة. "
        "رد CUCM موجود في سجل النشاط. أعد تشغيل Cisco TFTP من Cisco Unified Serviceability ثم Tools ثم "
        "Control Center - Feature Services.",
    "reading the List.xml files on the server…":"جارٍ قراءة ملفات List.xml على الخادم…",
    "A List.xml already in these folders is replaced.":"سيُستبدل ملف List.xml الموجود في هذه المجلدات.",
    "Cisco TFTP restarts on each node afterwards.": "ستُعاد بعد ذلك تشغيل خدمة Cisco TFTP على كل عقدة.",
    "signing in…": "جارٍ تسجيل الدخول…",
    "uploading {done}/{total}…": "جارٍ الرفع {done}/{total}…",
    "restarting Cisco TFTP…": "جارٍ إعادة تشغيل Cisco TFTP…",
    "checking the phones can fetch List.xml…": "جارٍ التحقق من أن الهواتف تستطيع جلب List.xml…",
    "uploaded; phones get the new pictures": "تم الرفع، وستحصل الهواتف على الصور الجديدة",
    "uploaded; TFTP still serves the old List.xml - restart Cisco TFTP":
        "تم الرفع، لكن TFTP ما زال يقدم List.xml القديم. أعد تشغيل Cisco TFTP",
    "Uploaded to {good} of {n} TFTP servers": "تم الرفع إلى {good} من {n} خادم TFTP",
    "Upload failed on {n} TFTP server(s). See the TFTP servers list and the activity log.":
        "فشل الرفع على {n} خادم TFTP. راجع قائمة خوادم TFTP وسجل النشاط.",
}
