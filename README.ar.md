# تذكير القرآن — Jisr Quran Reminder

برنامج لينكس يعرض آية من القرآن كل خمس دقائق، ويحفظ مكانك في القراءة، ويعمل
بدون إنترنت بعد التنزيل. [English documentation](README.md)

## التثبيت على أوبونتو مع GNOME وWayland

الإضافة تستهدف GNOME من 45 إلى 50. تم اختبارها على Ubuntu 24.04 مع GNOME 46
وعلى Ubuntu 26.04 مع GNOME 50 باستخدام جلسات Wayland فعلية داخل بيئات معزولة.
نسخة GNOME الافتراضية في Ubuntu 22.04 غير مدعومة بالإضافة الحالية.

افتح التيرمنال ونفّذ:

```sh
sudo apt update
sudo apt install git python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-gtklayershell-0.1 librsvg2-common fonts-noto-core
git clone https://github.com/Elgedawy31/quran-reminder.git
cd quran-reminder
./install.sh
```

في أول تثبيت، اعمل تسجيل خروج وادخل من جديد، ثم فعّل الإضافة:

```sh
gnome-extensions enable jisr-quran@elgedawy31.github.io
~/.local/bin/jisr-quran --show
```

يمكنك تفعيل **Jisr Quran Reminder** من تطبيق Extensions أيضًا.
المثبت يحاول تفعيلها مباشرة؛ GNOME على Wayland قد يحتاج تسجيل دخول جديد حتى
يتعرّف على الإضافة. بدون تفعيل الإضافة، الخدمة تعمل ولكن الكارت لا يظهر.

## باقي توزيعات لينكس

بعد تثبيت `git` بمدير حزم توزيعتك:

```sh
git clone https://github.com/Elgedawy31/quran-reminder.git
cd quran-reminder
./scripts/install-deps.sh
./install.sh
```

سكربت المكتبات يدعم Ubuntu/Debian وFedora وArch ومشتقاتها. على Arch ينفذ
تحديثًا كاملًا للنظام لتجنب التحديث الجزئي. يحتاج البرنامج جلسة سطح مكتب مع
systemd وD-Bus؛ الأنظمة المختلفة مثل NixOS تحتاج إعدادًا مخصصًا.

البرنامج يختار طريقة العرض تلقائيًا: إضافة GNOME، أو Layer Shell على niri وSway
وHyprland وKDE Wayland، أو نافذة GTK عادية على X11. يمكن اختيار نافذة عادية
يدويًا بأمر `./install.sh --backend window`؛ على Wayland تموضعها وبقاؤها فوق
النوافذ يتوقفان على مدير النوافذ.

يمكن التنزيل بدون Git من [صفحة الإصدارات](https://github.com/Elgedawy31/quran-reminder/releases/latest):

```sh
sha256sum --ignore-missing -c SHA256SUMS
tar -xzf quran-reminder-0.1.0.tar.gz
cd quran-reminder-0.1.0
./scripts/install-deps.sh
./install.sh
```

نزّل الأرشيف وملف `SHA256SUMS` أولًا. على GNOME طبّق خطوة تفعيل الإضافة أيضًا.
تم اختبار Ubuntu 24.04 مع GNOME 46 وUbuntu 26.04 مع GNOME 50 وWayland فعليًا داخل بيئات معزولة، وكذلك
واجهة GTK على X11. وصفات Fedora وArch متاحة ولم تختبر هنا على سطح مكتب كامل.

## الاستخدام

- **تمت القراءة:** يسجل قراءتك ويغلق الكارت. بعد خمس دقائق تظهر الآية التالية.
- **إخفاء:** يغلق الكارت بدون تسجيل قراءة. نفس الآية تعود بعد خمس دقائق.
- لو تركت الكارت مفتوحًا، الآية لا تتغير تلقائيًا.
- الآية الطويلة تظهر كاملة مع التمرير. الكارت لا يسحب تركيز الكيبورد.
- البرنامج يبدأ مع تسجيل الدخول، ويحتفظ بتقدم القراءة بعد إعادة التشغيل.

```sh
~/.local/bin/jisr-quran --show
~/.local/bin/jisr-quran --hide
~/.local/bin/jisr-quran --stop
~/.local/bin/jisr-quran --start
~/.local/bin/jisr-quran --status
```

الإيقاف بأمر `--stop` يستمر بعد تسجيل الدخول، حتى تعيد التشغيل بـ `--start`.
يمكن استخدام اختصارات **Quran Reminder** و **Quran Reminder Stop** من قائمة التطبيقات.

المدة في `~/.config/jisr-quran/config.json`؛ القيمة `300` تعني خمس دقائق.
بعد تغييرها، أعد تشغيل الخدمة:

```sh
systemctl --user restart jisr-quran.service
```

## التحديث والإزالة

من مجلد المشروع:

```sh
git pull --ff-only
./install.sh
systemctl --user restart jisr-quran.service
```

بعد تحديث إضافة GNOME اعمل تسجيل خروج ودخول لتحميل الكود الجديد.
الإعدادات وتقدم القراءة محفوظان أثناء التحديث.

```sh
./install.sh --uninstall
```

الإزالة تحتفظ بالإعدادات وتقدم القراءة. لا تشغّل المثبّت باستخدام `sudo`؛
التثبيت يتم لحسابك فقط. استخدام `sudo` مطلوب لتثبيت مكتبات النظام فقط.

راجع [الدليل الكامل](README.md) لمعرفة التشخيص ومصادر النص والترخيص.
