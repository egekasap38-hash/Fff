from pathlib import Path
root=Path("CamonWalk/app/src/main")
p=root/"java/com/camonwalk/app/StepWriterService.kt"
s=p.read_text()
s=s.replace("import androidx.health.connect.client.records.StepsRecord","import androidx.health.connect.client.records.StepsRecord\nimport androidx.health.connect.client.records.DistanceRecord\nimport androidx.health.connect.client.units.Length")
s=s.replace('const val KEY_ERROR = "error"','const val KEY_ERROR = "error"\n        const val KEY_VERIFIED = "verified"')
s=s.replace('.putInt(KEY_WRITTEN, 0).putLong(KEY_START, now)','.putInt(KEY_WRITTEN, 0).putInt(KEY_VERIFIED, 0).putLong(KEY_START, now)')
s=s.replace('val permission = HealthPermission.getWritePermission(StepsRecord::class)','val permissions = setOf(HealthPermission.getWritePermission(StepsRecord::class),\n                HealthPermission.getWritePermission(DistanceRecord::class))')
s=s.replace('if (permission !in client.permissionController.getGrantedPermissions()) {','if (!client.permissionController.getGrantedPermissions().containsAll(permissions)) {')
s=s.replace('throw IllegalStateException("Health Connect adım yazma izni verilmedi")','throw IllegalStateException("Health Connect adım ve mesafe yazma izni gerekli")')
s=s.replace('''// Yazma tamamlanmadan ilerleme sayacı artırılmaz.
                    client.insertRecords(listOf(record))
                    prefs.edit().putInt(KEY_WRITTEN, desired).putLong(KEY_LAST_END, now).commit()''','''// Manuel test kaydıdır, gerçek sensör ölçümü değildir.
                    val distance = DistanceRecord(
                        startTime = intervalStart, endTime = intervalEnd,
                        startZoneOffset = zone.rules.getOffset(intervalStart),
                        endZoneOffset = zone.rules.getOffset(intervalEnd),
                        distance = Length.meters(delta.toDouble() * 0.75),
                        metadata = Metadata.manualEntry()
                    )
                    val result = client.insertRecords(listOf(record, distance))
                    val savedId = result.recordIdsList.firstOrNull()
                        ?: throw IllegalStateException("Health Connect kayıt kimliği döndürmedi")
                    val saved = client.readRecord(StepsRecord::class, savedId).record
                    if (saved.count != delta.toLong()) {
                        throw IllegalStateException("Health Connect kaydı doğrulanamadı")
                    }
                    prefs.edit().putInt(KEY_WRITTEN, desired).putInt(KEY_VERIFIED, desired)
                        .putLong(KEY_LAST_END, now).commit()''')
p.write_text(s)

p=root/"java/com/camonwalk/app/MainActivity.kt"
s=p.read_text()
s=s.replace('import androidx.health.connect.client.records.StepsRecord','import androidx.health.connect.client.records.StepsRecord\nimport androidx.health.connect.client.records.DistanceRecord')
s=s.replace('private val stepsPermission = HealthPermission.getWritePermission(StepsRecord::class)','private val stepsPermission = HealthPermission.getWritePermission(StepsRecord::class)\n    private val distancePermission = HealthPermission.getWritePermission(DistanceRecord::class)\n    private val healthPermissions get() = setOf(stepsPermission, distancePermission)')
s=s.replace('if (stepsPermission in granted) {','if (granted.containsAll(healthPermissions)) {')
s=s.replace('if (stepsPermission !in granted) {','if (!granted.containsAll(healthPermissions)) {')
s=s.replace('healthPermissionLauncher.launch(setOf(stepsPermission))','healthPermissionLauncher.launch(healthPermissions)')
s=s.replace('permissionButton.setOnClickListener { ensureHealthPermission(false) }','''permissionButton.setOnClickListener { ensureHealthPermission(false) }
        findViewById<Button>(R.id.fitButton).setOnClickListener {
            val fitIntent = packageManager.getLaunchIntentForPackage("com.google.android.apps.fitness")
            if (fitIntent != null) startActivity(fitIntent)
            else startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(
                "https://play.google.com/store/apps/details?id=com.google.android.apps.fitness")))
        }''')
s=s.replace('val done = p.getInt(StepWriterService.KEY_WRITTEN, 0)','val done = p.getInt(StepWriterService.KEY_WRITTEN, 0)\n        val verified = p.getInt(StepWriterService.KEY_VERIFIED, 0)')
s=s.replace("isRunning -> \"Çalışıyor • Health Connect'e aşamalı kaydediliyor\"", "isRunning -> \"Çalışıyor • $verified adım kaydı doğrulandı\"")
s=s.replace('target > 0 && done >= target -> "Tamamlandı • $done adım kaydedildi"','target > 0 && done >= target -> "Tamamlandı • $verified adım kaydı doğrulandı"')
s=s.replace('target > 0 -> "Durduruldu • $done adım kaydedildi"','target > 0 -> "Durduruldu • $verified adım kaydı doğrulandı"')
p.write_text(s)

p=root/"AndroidManifest.xml"
s=p.read_text().replace('<uses-permission android:name="android.permission.health.WRITE_STEPS" />','<uses-permission android:name="android.permission.health.WRITE_STEPS" />\n    <uses-permission android:name="android.permission.health.WRITE_DISTANCE" />').replace('<package android:name="com.google.android.apps.healthdata" />','<package android:name="com.google.android.apps.healthdata" />\n        <package android:name="com.google.android.apps.fitness" />')
p.write_text(s)

p=root/"res/values/health_permissions.xml"
s=p.read_text().replace('<item>android.permission.health.WRITE_STEPS</item>','<item>android.permission.health.WRITE_STEPS</item>\n        <item>android.permission.health.WRITE_DISTANCE</item>')
p.write_text(s)

p=root/"res/layout/activity_main.xml"
s=p.read_text()
s=s.replace('            <Button android:id="@+id/permissionButton"','''            <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
                android:layout_marginTop="14dp" android:text="Senkron modu: seçilen süre boyunca adım ve tahmini mesafe kaydı."
                android:textColor="@color/muted" android:textSize="13sp" />
            <Button android:id="@+id/permissionButton"''')
s=s.replace('        <TextView android:layout_width="match_parent" android:layout_height="wrap_content"\n            android:layout_marginTop="18dp" android:layout_marginBottom="32dp"','''        <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content"
            android:layout_marginTop="18dp" android:background="@drawable/bg_card"
            android:orientation="vertical" android:padding="18dp">
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
                android:text="GOOGLE FIT EŞİTLEME" android:textColor="@color/mint"
                android:textStyle="bold" android:textSize="15sp" />
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
                android:layout_marginTop="10dp" android:textColor="@color/white"
                android:text="Google Fit: Profil > Ayarlar > Health Connect > Fit ile senkronize et. Bu seçenek açık değilse kayıtlar Fit'te görünmeyebilir."
                android:textSize="13sp" />
            <Button android:id="@+id/fitButton" android:layout_width="match_parent"
                android:layout_height="52dp" android:layout_marginTop="14dp"
                android:background="@drawable/bg_button_secondary" android:text="Google Fit'i aç"
                android:textAllCaps="false" android:textColor="@color/white" />
        </LinearLayout>
        <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
            android:layout_marginTop="18dp" android:layout_marginBottom="32dp"''')
s=s.replace("Adımlar Health Connect'e elle girilmiş test kaydı olarak yazılır.","Adımlar ve tahmini mesafe Health Connect'e manuel test kaydı olarak yazılır, ardından geri okunarak doğrulanır.")
p.write_text(s)
