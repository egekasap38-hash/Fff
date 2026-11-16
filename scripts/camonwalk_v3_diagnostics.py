from pathlib import Path
root = Path("CamonWalk/app/src/main")
p = root / "AndroidManifest.xml"
s = p.read_text()
s = s.replace('<uses-permission android:name="android.permission.health.WRITE_STEPS" />',
              '<uses-permission android:name="android.permission.health.WRITE_STEPS" />\n    <uses-permission android:name="android.permission.health.READ_STEPS" />')
p.write_text(s)

p = root / "res/values/health_permissions.xml"
s = p.read_text()
s = s.replace('<item>android.permission.health.WRITE_STEPS</item>',
              '<item>android.permission.health.WRITE_STEPS</item>\n        <item>android.permission.health.READ_STEPS</item>')
p.write_text(s)

p = root / "java/com/camonwalk/app/MainActivity.kt"
s = p.read_text()
s = s.replace('import androidx.health.connect.client.records.StepsRecord',
    'import androidx.health.connect.client.records.StepsRecord\n' +
    'import androidx.health.connect.client.aggregate.AggregateRequest\n' +
    'import androidx.health.connect.client.time.TimeRangeFilter\n' +
    'import androidx.health.connect.client.records.metadata.DataOrigin\n' +
    'import java.time.Instant\nimport java.time.LocalDate\nimport java.time.ZoneId')
s = s.replace('private val healthPermissions get() = setOf(stepsPermission, distancePermission)',
              'private val readPermission = HealthPermission.getReadPermission(StepsRecord::class)\n' +
              '    private val healthPermissions get() = setOf(stepsPermission, distancePermission, readPermission)')
s = s.replace('permissionButton.setOnClickListener { ensureHealthPermission(false) }',
'''permissionButton.setOnClickListener { ensureHealthPermission(false) }
        findViewById<Button>(R.id.verifyButton).setOnClickListener { verifyHealthEntries() }
        findViewById<Button>(R.id.healthButton).setOnClickListener {
            try {
                startActivity(Intent(HealthConnectClient.ACTION_HEALTH_CONNECT_SETTINGS))
            } catch (e: Exception) {
                toast("Health Connect açılamadı: " + (e.localizedMessage ?: "Bilinmeyen hata"))
            }
        }''')
anchor='    private fun refreshProgress() {'
assert anchor in s
func='''    private fun verifyHealthEntries() {
        val verification = findViewById<TextView>(R.id.verifyStatus)
        verification.text = "Health Connect verileri okunuyor..."
        lifecycleScope.launch {
            try {
                val client = HealthConnectClient.getOrCreate(this@MainActivity)
                val granted = client.permissionController.getGrantedPermissions()
                if (readPermission !in granted) {
                    verification.text = "Adım okuma izni gerekli. İzni verip tekrar kontrol et."
                    healthPermissionLauncher.launch(healthPermissions)
                    return@launch
                }
                val startDay = LocalDate.now().atStartOfDay(ZoneId.systemDefault()).toInstant()
                val endDay = Instant.now()
                val interval = TimeRangeFilter.between(startDay, endDay)
                val own = client.aggregate(AggregateRequest(
                    metrics = setOf(StepsRecord.COUNT_TOTAL),
                    timeRangeFilter = interval,
                    dataOriginFilter = setOf(DataOrigin(packageName))
                ))[StepsRecord.COUNT_TOTAL] ?: 0L
                val total = client.aggregate(AggregateRequest(
                    metrics = setOf(StepsRecord.COUNT_TOTAL),
                    timeRangeFilter = interval
                ))[StepsRecord.COUNT_TOTAL] ?: 0L
                verification.text =
                    "Bugün CamonWalk kayıtları: " + own + " adım\\n" +
                    "Health Connect birleşik toplam: " + total + " adım\\n" +
                    (if (own > 0 && total < own) "Kayıt var ancak toplamda kaynak önceliği etkili olabilir."
                     else if (own == 0L) "Bugün için CamonWalk adım kaydı bulunamadı."
                     else "Kayıtlar Health Connect içinden okunabildi.") +
                    "\\nGoogle Fit'teki sayı ayrı bir uygulamadır; senkronizasyon garanti değildir."
            } catch (e: Exception) {
                verification.text = "Kayıt sorgulama hatası: " +
                    (e.localizedMessage ?: e.javaClass.simpleName)
            }
        }
    }

'''
s = s.replace(anchor, func+anchor)
p.write_text(s)

p = root / "res/layout/activity_main.xml"
s = p.read_text()
marker = '        <TextView android:layout_width="match_parent" android:layout_height="wrap_content"\n            android:layout_marginTop="18dp" android:layout_marginBottom="32dp"'
assert marker in s
addon = '''        <LinearLayout android:layout_width="match_parent"
            android:layout_height="wrap_content" android:layout_marginTop="18dp"
            android:background="@drawable/bg_card" android:orientation="vertical"
            android:padding="18dp">
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
                android:text="VERİ KONTROLÜ" android:textColor="@color/mint"
                android:textStyle="bold" android:textSize="15sp" />
            <TextView android:id="@+id/verifyStatus" android:layout_width="match_parent"
                android:layout_height="wrap_content" android:layout_marginTop="12dp"
                android:text="Kayıtların günlük toplamda görünüp görünmediğini kontrol et."
                android:textColor="@color/white" android:textSize="13sp" />
            <Button android:id="@+id/verifyButton" android:layout_width="match_parent"
                android:layout_height="52dp" android:layout_marginTop="12dp"
                android:background="@drawable/bg_button_primary"
                android:text="Kayıtları Kontrol Et" android:textAllCaps="false"
                android:textColor="@color/navy" />
            <Button android:id="@+id/healthButton" android:layout_width="match_parent"
                android:layout_height="52dp" android:layout_marginTop="10dp"
                android:background="@drawable/bg_button_secondary"
                android:text="Health Connect'i Aç" android:textAllCaps="false"
                android:textColor="@color/white" />
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
                android:layout_marginTop="10dp" android:textColor="@color/muted"
                android:textSize="12sp"
                android:text="Health Connect &gt; Veriler ve erişim &gt; Etkinlik &gt; Adımlar &gt; Tüm kayıtlar. Toplam sayıya etki etmiyorsa Veri kaynakları ve öncelik bölümünü kontrol et." />
        </LinearLayout>
'''
s=s.replace(marker,addon+marker)
p.write_text(s)

p = Path("CamonWalk/app/build.gradle.kts")
s=p.read_text()
s=s.replace('versionCode = 1','versionCode = 3').replace('versionName = "1.0"','versionName = "3.0"')
p.write_text(s)
