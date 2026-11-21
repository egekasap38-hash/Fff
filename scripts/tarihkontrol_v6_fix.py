from pathlib import Path

src = Path("TarihKontrolOverlay/app/src/main/java/com/ege/tarihkontrol/OverlayService.java")
s = src.read_text(encoding="utf-8")

fixes = [
    ("import rikka.shizuku.Shizuku;",
     "import rikka.shizuku.Shizuku;\nimport rikka.shizuku.ShizukuRemoteProcess;"),
    ("if (!process.waitFor(8, TimeUnit.SECONDS)) {",
     """// ShizukuRemoteProcess requires its own timed wait implementation.
        boolean completed;
        if (process instanceof ShizukuRemoteProcess) {
            completed = ((ShizukuRemoteProcess) process).waitForTimeout(8, TimeUnit.SECONDS);
        } else {
            completed = process.waitFor(8, TimeUnit.SECONDS);
        }
        if (!completed) {"""),
    ('            String result;\n            boolean returned = false;',
     '            String result;\n            boolean returned = false;\n            String stage = "oyunu algılama";'),
    ('                    ShellResult home = shell("input keyevent KEYCODE_HOME");',
     '                    stage = "ana ekrana geçiş";\n                    ShellResult home = shell("input keyevent KEYCODE_HOME");'),
    ('                        ShellResult change = shell(command);',
     '                        stage = "tarih ayarlama";\n                        ShellResult change = shell(command);'),
    ('                        ShellResult resume = shell("am start --activity-reorder-to-front --activity-single-top -n " + foreground);',
     '                        stage = "oyuna dönüş";\n                        ShellResult resume = shell("am start --activity-reorder-to-front --activity-single-top -n " + foreground);'),
    ('                result = "İşlem başarısız: " + e.getClass().getSimpleName();',
     """                Throwable cause = e;
                if (e instanceof java.lang.reflect.InvocationTargetException && e.getCause() != null) {
                    cause = e.getCause();
                }
                result = "Hata (" + stage + "): " + cause.getClass().getSimpleName()
                        + (cause.getMessage() == null ? "" : " - " + shortText(cause.getMessage()));"""),
]

for old, replacement in fixes:
    assert old in s, f"Missing expected anchor: {old[:65]}"
    s = s.replace(old, replacement, 1)
src.write_text(s, encoding="utf-8")

gradle = Path("TarihKontrolOverlay/app/build.gradle")
g = gradle.read_text(encoding="utf-8")
assert 'versionCode 5' in g and "versionName '5.0-draggable'" in g
g = g.replace('versionCode 5', 'versionCode 6')
g = g.replace("versionName '5.0-draggable'", "versionName '6.0-shizuku-fix'")
gradle.write_text(g, encoding="utf-8")
print("v6 Shizuku timeout fix applied")
