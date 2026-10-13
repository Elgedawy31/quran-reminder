# تذكير القرآن — Jisr Quran Reminder

برنامج لينكس يعرض آية من القرآن كل خمس دقائق، ويحفظ مكانك في القراءة، ويعمل
بدون إنترنت بعد التنزيل. [English documentation](README.md)

## التثبيت على أوبونتو مع GNOME وWayland

الإضافة تستهدف GNOME من 45 إلى 50، ومنها GNOME 46 على Ubuntu 24.04.
نسخة GNOME الافتراضية في Ubuntu 22.04 غير مدعومة بالإضافة الحالية.

افتح التيرمنال ونفّذ:

```sh
sudo apt update
sudo apt install git python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-gtklayershell-0.1 fonts-noto-core
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
