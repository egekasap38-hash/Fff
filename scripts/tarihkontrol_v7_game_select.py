from pathlib import Path

base = Path("TarihKontrolOverlay/app/src/main")
main_file = base / "java/com/ege/tarihkontrol/MainActivity.java"
service_file = base / "java/com/ege/tarihkontrol/OverlayService.java"
manifest_file = base / "AndroidManifest.xml"
build_file = Path("TarihKontrolOverlay/app/build.gradle")

s = main_file.read_text(encoding="utf-8")

def replace_once(text, needle, replacement):
    assert text.count(needle) == 1, "Anchor missing or repeated: " + needle[:75]
    return text.replace(needle, replacement, 1)

s = replace_once(s, "import android.app.Activity;",
"""import android.app.Activity;
import android.app.AlertDialog;
import android.content.ComponentName;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.ResolveInfo;
import android.graphics.drawable.Drawable;
import android.text.Editable;
import android.text.TextWatcher;
import android.widget.BaseAdapter;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.ListView;
import android.widget.Toast;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;""")
s = replace_once(s, "    private Button resetButton;",
"""    private Button resetButton;
    private Button gameButton;
    private TextView gameStatus;
    private static final String GAME_PREFS = "tarih_game_selection_v7";""")
s = replace_once(s, "        permissionButton = actionButton(",
"""        gameButton = actionButton("🎮  Oyun seç", 0xFF244E8B);
        LinearLayout.LayoutParams gameLp = new LinearLayout.LayoutParams(-1, dp(56));
        gameLp.topMargin = dp(14);
        root.addView(gameButton, gameLp);
        gameButton.setOnClickListener(v -> showGameChooser());
        gameStatus = label("", 13, 0xFFC9D9F4, false);
        gameStatus.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams gameStatusLp = new LinearLayout.LayoutParams(-1, dp(36));
        root.addView(gameStatus, gameStatusLp);
        permissionButton = actionButton(""")
s = replace_once(s, "        overlayButton.setText(OverlayService.running ?",
"""        updateGameStatus();
        overlayButton.setText(OverlayService.running ?""")
s = replace_once(s, "    private void toggleOverlay() {",
"""    private void updateGameStatus() {
        if (gameStatus == null) return;
        SharedPreferences sp = getSharedPreferences(GAME_PREFS, MODE_PRIVATE);
        String selectedName = sp.getString("game_label", "");
        String selectedPackage = sp.getString("game_package", "");
        if (selectedPackage.isEmpty()) {
            gameStatus.setText("Henüz oyun seçilmedi");
            gameButton.setText("🎮  Oyun seç");
        } else {
            gameStatus.setText("Seçili: " + selectedName);
            gameButton.setText("🎮  Oyunu değiştir");
        }
    }

    private static class GameEntry {
        String label;
        String pkg;
        String component;
        Drawable icon;
        boolean isGame;
        GameEntry(String label, String pkg, String component, Drawable icon, boolean isGame) {
            this.label = label; this.pkg = pkg; this.component = component;
            this.icon = icon; this.isGame = isGame;
        }
    }

    private List<GameEntry> availableGamesAndApps() {
        PackageManager pm = getPackageManager();
        Intent query = new Intent(Intent.ACTION_MAIN);
        query.addCategory(Intent.CATEGORY_LAUNCHER);
        List<ResolveInfo> installed = pm.queryIntentActivities(query, 0);
        List<GameEntry> apps = new ArrayList<>();
        HashSet<String> seen = new HashSet<>();
        for (ResolveInfo info : installed) {
            if (info.activityInfo == null) continue;
            String pkg = info.activityInfo.packageName;
            if (pkg.equals(getPackageName()) || !seen.add(pkg)) continue;
            try {
                String label = String.valueOf(info.loadLabel(pm)).trim();
                if (label.isEmpty()) label = pkg;
                String name = info.activityInfo.name;
                if (name.startsWith(".")) name = pkg + name;
                String component = new ComponentName(pkg, name).flattenToString();
                ApplicationInfo application = pm.getApplicationInfo(pkg, 0);
                boolean game = application.category == ApplicationInfo.CATEGORY_GAME;
                apps.add(new GameEntry(label, pkg, component, info.loadIcon(pm), game));
            } catch (Exception ignored) {}
        }
        Collections.sort(apps, (a, b) -> {
            if (a.isGame != b.isGame) return a.isGame ? -1 : 1;
            return a.label.compareToIgnoreCase(b.label);
        });
        return apps;
    }

    private class GameAdapter extends BaseAdapter {
        private final List<GameEntry> all;
        private final List<GameEntry> visible = new ArrayList<>();
        GameAdapter(List<GameEntry> apps) { all = apps; visible.addAll(apps); }
        void filter(String query) {
            visible.clear();
            String term = query.trim().toLowerCase(Locale.ROOT);
            for (GameEntry app : all) {
                if (app.label.toLowerCase(Locale.ROOT).contains(term) ||
                        app.pkg.toLowerCase(Locale.ROOT).contains(term)) {
                    visible.add(app);
                }
            }
            notifyDataSetChanged();
        }
        @Override public int getCount() { return visible.size(); }
        @Override public GameEntry getItem(int position) { return visible.get(position); }
        @Override public long getItemId(int position) { return position; }
        @Override public View getView(int position, View old, android.view.ViewGroup parent) {
            GameEntry item = getItem(position);
            LinearLayout row = new LinearLayout(MainActivity.this);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(dp(12), dp(7), dp(8), dp(7));
            ImageView image = new ImageView(MainActivity.this);
            image.setImageDrawable(item.icon);
            row.addView(image, new LinearLayout.LayoutParams(dp(42), dp(42)));
            LinearLayout column = new LinearLayout(MainActivity.this);
            column.setOrientation(LinearLayout.VERTICAL);
            column.setPadding(dp(14), 0, 0, 0);
            TextView name = label(item.label, 16, Color.WHITE, true);
            TextView packageName = label(item.pkg, 11, 0xFFAABBCD, false);
            column.addView(name);
            column.addView(packageName);
            row.addView(column, new LinearLayout.LayoutParams(-1, -2));
            return row;
        }
    }

    private void showGameChooser() {
        List<GameEntry> apps = availableGamesAndApps();
        if (apps.isEmpty()) {
            Toast.makeText(this, "Yüklü oyun veya uygulama bulunamadı", Toast.LENGTH_LONG).show();
            return;
        }
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(16), 0, dp(16), dp(8));

        EditText search = new EditText(this);
        search.setSingleLine(true);
        search.setHint("Oyun adını ara...");
        search.setTextColor(Color.WHITE);
        search.setHintTextColor(0xFF9EB0C9);
        panel.addView(search, new LinearLayout.LayoutParams(-1, dp(54)));

        ListView list = new ListView(this);
        list.setDividerHeight(dp(1));
        GameAdapter adapter = new GameAdapter(apps);
        list.setAdapter(adapter);
        panel.addView(list, new LinearLayout.LayoutParams(-1, dp(350)));

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("Oyun seç")
                .setView(panel)
                .setNegativeButton("İptal", null)
                .setNeutralButton("Seçimi kaldır", (d, which) -> {
                    getSharedPreferences(GAME_PREFS, MODE_PRIVATE).edit().clear().apply();
                    updateGameStatus();
                }).create();

        list.setOnItemClickListener((parent, view, position, id) -> {
            GameEntry chosen = adapter.getItem(position);
            getSharedPreferences(GAME_PREFS, MODE_PRIVATE).edit()
                    .putString("game_package", chosen.pkg)
                    .putString("game_component", chosen.component)
                    .putString("game_label", chosen.label)
                    .apply();
            updateGameStatus();
            Toast.makeText(this, "Seçilen oyun: " + chosen.label, Toast.LENGTH_SHORT).show();
            dialog.dismiss();
        });
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) {
                adapter.filter(s.toString());
            }
            @Override public void afterTextChanged(Editable s) {}
        });
        dialog.show();
    }

    private void toggleOverlay() {
        if (!hasSelectedGame()) {
            showGameChooser();
            return;
        }""")
# Before overlay stop? keep stop ability when selection cleared:
s = s.replace("""    private void toggleOverlay() {
        if (!hasSelectedGame()) {
            showGameChooser();
            return;
        }
        if (OverlayService.running) {""",
"""    private boolean hasSelectedGame() {
        return !getSharedPreferences(GAME_PREFS, MODE_PRIVATE).getString("game_package", "").isEmpty();
    }

    private void toggleOverlay() {
        if (OverlayService.running) {
            stopService(new Intent(this, OverlayService.class));
            overlayButton.postDelayed(this::refresh, 200);
            return;
        }
        if (!hasSelectedGame()) {
            showGameChooser();
            return;
        }
        if (false) {""")
# Remove redundant unreachable block introduced by the inversion
s = replace_once(s, """        if (false) {
            stopService(new Intent(this, OverlayService.class));
            overlayButton.postDelayed(this::refresh, 200);
            return;
        }
        if (!shizukuReady())""", """        if (!shizukuReady())""")

main_file.write_text(s, encoding="utf-8")

s = service_file.read_text(encoding="utf-8")
s = replace_once(s, '    private static final String APP_PACKAGE = "com.ege.tarihkontrol";',
"""    private static final String APP_PACKAGE = "com.ege.tarihkontrol";
    private static final String GAME_PREFS = "tarih_game_selection_v7";""")
s = replace_once(s, """        new Thread(() -> {
            String result;
            boolean returned = false;
            String stage = "oyunu algılama";""",
"""        final SharedPreferences selected = getSharedPreferences(GAME_PREFS, MODE_PRIVATE);
        final String chosenPackage = selected.getString("game_package", "");
        final String chosenComponent = selected.getString("game_component", "");
        if (chosenPackage == null || chosenComponent == null
                || !chosenPackage.matches("[A-Za-z0-9_]+(\\\\.[A-Za-z0-9_]+)+")
                || !chosenComponent.startsWith(chosenPackage + "/")) {
            message("Önce uygulamadan oyun seç");
            busy.set(false);
            return;
        }
        new Thread(() -> {
            String result;
            boolean returned = false;
            String stage = "seçili oyunu kontrol";""")
s = replace_once(s, """                // Capture the currently running activity before moving to the home screen.
                String foreground = findForegroundComponent();
                if (foreground == null) {
                    result = "Açık oyun tespit edilemedi; işlem yapılmadı";
                } else {""",
"""                String foreground = null;
                try { foreground = findForegroundComponent(); } catch (Exception ignored) {}
                String returnComponent = foreground != null && foreground.startsWith(chosenPackage + "/")
                        ? foreground : chosenComponent;
                if (getPackageManager().getLaunchIntentForPackage(chosenPackage) == null) {
                    result = "Seçilen oyun kaldırılmış veya başlatılamıyor; yeniden seç";
                } else {""")
s = replace_once(s, 'shell("am start --activity-reorder-to-front --activity-single-top -n " + foreground)',
                    'shell("am start --activity-reorder-to-front --activity-single-top -n " + returnComponent)')
s = replace_once(s, """                            String pkg = foreground.substring(0, foreground.indexOf('/'));
                            ShellResult fallback = shell("monkey -p " + pkg + " -c android.intent.category.LAUNCHER 1");""",
"""                            ShellResult fallback = shell("monkey -p " + chosenPackage + " -c android.intent.category.LAUNCHER 1");""")
service_file.write_text(s, encoding="utf-8")

m = manifest_file.read_text(encoding="utf-8")
m = replace_once(m, '<application', """<queries>
        <intent>
            <action android:name="android.intent.action.MAIN" />
            <category android:name="android.intent.category.LAUNCHER" />
        </intent>
    </queries>
    <application""")
manifest_file.write_text(m, encoding="utf-8")

g = build_file.read_text(encoding="utf-8")
assert "versionCode 6" in g and "versionName '6.0-shizuku-fix'" in g
g = g.replace("versionCode 6", "versionCode 7")
g = g.replace("versionName '6.0-shizuku-fix'", "versionName '7.0-game-select'")
build_file.write_text(g, encoding="utf-8")
print("v7 game selection applied")
