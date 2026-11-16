from pathlib import Path
root = Path("CamonWalk/app/src/main")
service = r'''package com.camonwalk.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.records.DistanceRecord
import androidx.health.connect.client.records.metadata.Metadata
import androidx.health.connect.client.units.Length
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneId
import kotlin.math.min
import kotlin.math.max

/** Health Connect'e manuel test kayıtları ekler; gerçek adım sensörü verisi üretmez. */
class StepWriterService : Service() {
    companion object {
        const val PREFS = "camonwalk_session"
        const val KEY_ACTIVE = "active"
        const val KEY_TARGET = "target"
        const val KEY_WRITTEN = "written"
        const val KEY_VERIFIED = "verified"
        const val KEY_START = "start_ms"
        const val KEY_LAST_END = "last_end_ms"
        const val KEY_RATE = "rate"
        const val KEY_UNIT = "unit"
        const val KEY_UNLIMITED = "unlimited"
        const val KEY_ERROR = "error"
        const val ACTION_START = "com.camonwalk.app.START"
        const val ACTION_STOP = "com.camonwalk.app.STOP"
        const val EXTRA_STEPS = "steps"
        const val EXTRA_RATE = "rate"
        const val EXTRA_UNIT = "unit"
        const val EXTRA_UNLIMITED = "unlimited"
        private const val CHANNEL = "camonwalk_steps"
        private const val NOTIFICATION_ID = 27
    }
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var job: Job? = null
    private val prefs by lazy { getSharedPreferences(PREFS, MODE_PRIVATE) }

    override fun onBind(intent: Intent?): IBinder? = null
    override fun onCreate() {
        super.onCreate()
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(
            NotificationChannel(CHANNEL, "Adım kayıt hizmeti", NotificationManager.IMPORTANCE_LOW)
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            prefs.edit().putBoolean(KEY_ACTIVE, false).commit()
            job?.cancel()
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return START_NOT_STICKY
        }
        if (intent?.action == ACTION_START) {
            val target = intent.getIntExtra(EXTRA_STEPS, 0)
            val rate = intent.getIntExtra(EXTRA_RATE, 0)
            val unit = intent.getIntExtra(EXTRA_UNIT, 0)
            val unlimited = intent.getBooleanExtra(EXTRA_UNLIMITED, false)
            val validRate = if (unit == 1) rate in 1..200 else rate in 1..10000
            if (!validRate || unit !in 0..1 ||
                (!unlimited && target !in 1..2000000000) ||
                prefs.getBoolean(KEY_ACTIVE, false)) {
                if (job == null) stopSelf()
                return START_NOT_STICKY
            }
            val now = System.currentTimeMillis()
            prefs.edit().putBoolean(KEY_ACTIVE, true)
                .putInt(KEY_TARGET, if (unlimited) 0 else target)
                .putBoolean(KEY_UNLIMITED, unlimited)
                .putInt(KEY_RATE, rate).putInt(KEY_UNIT, unit)
                .putLong(KEY_WRITTEN, 0L).putLong(KEY_VERIFIED, 0L)
                .putLong(KEY_START, now).putLong(KEY_LAST_END, now)
                .putString(KEY_ERROR, "").commit()
        }
        if (!prefs.getBoolean(KEY_ACTIVE, false)) {
            stopSelf()
            return START_NOT_STICKY
        }
        try {
            val notification = createNotification(
                prefs.getLong(KEY_WRITTEN, 0L),
                prefs.getInt(KEY_TARGET, 0),
                prefs.getBoolean(KEY_UNLIMITED, false))
            if (Build.VERSION.SDK_INT >= 34) {
                startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_HEALTH)
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }
        } catch (e: Exception) {
            prefs.edit().putBoolean(KEY_ACTIVE, false).putString(
                KEY_ERROR, "Arka plan hizmeti açılamadı: " + e.localizedMessage).apply()
            stopSelf()
            return START_NOT_STICKY
        }
        if (job == null || job?.isCompleted == true) {
            job = scope.launch { writeSteps() }
        }
        return START_STICKY
    }

    private suspend fun writeSteps() {
        try {
            val client = HealthConnectClient.getOrCreate(this)
            val permissions = setOf(
                HealthPermission.getWritePermission(StepsRecord::class),
                HealthPermission.getWritePermission(DistanceRecord::class))
            if (!client.permissionController.getGrantedPermissions().containsAll(permissions)) {
                throw IllegalStateException("Health Connect adım ve mesafe yazma izni gerekli")
            }
            while (scope.isActive && prefs.getBoolean(KEY_ACTIVE, false)) {
                val now = System.currentTimeMillis()
                val start = prefs.getLong(KEY_START, now)
                val rate = prefs.getInt(KEY_RATE, 0).toLong()
                val unitMs = if (prefs.getInt(KEY_UNIT, 0) == 1) 1000.0 else 60000.0
                val unlimited = prefs.getBoolean(KEY_UNLIMITED, false)
                val target = prefs.getInt(KEY_TARGET, 0)
                val written = prefs.getLong(KEY_WRITTEN, 0L)
                if (rate <= 0) throw IllegalStateException("Geçersiz adım hızı")
                val elapsed = (now - start).coerceAtLeast(0L)
                val computed = (rate.toDouble() * elapsed.toDouble() / unitMs)
                    .coerceIn(0.0, (Long.MAX_VALUE - 100000L).toDouble()).toLong()
                val desired = if (unlimited) computed else min(target.toLong(), computed)
                val delta = (desired - written).coerceAtLeast(0L).coerceAtMost(10000L)
                if (delta > 0L) {
                    val lastEnd = prefs.getLong(KEY_LAST_END, start)
                    val from = Instant.ofEpochMilli(min(lastEnd, now - 1L))
                    val to = Instant.ofEpochMilli(max(now, lastEnd + 1L))
                    val zone = ZoneId.systemDefault()
                    val record = StepsRecord(
                        startTime = from, endTime = to,
                        startZoneOffset = zone.rules.getOffset(from),
                        endZoneOffset = zone.rules.getOffset(to),
                        count = delta,
                        metadata = Metadata.manualEntry()
                    )
                    val distance = DistanceRecord(
                        startTime = from, endTime = to,
                        startZoneOffset = zone.rules.getOffset(from),
                        endZoneOffset = zone.rules.getOffset(to),
                        distance = Length.meters(delta.toDouble() * 0.75),
                        metadata = Metadata.manualEntry()
                    )
                    val result = client.insertRecords(listOf(record, distance))
                    val id = result.recordIdsList.firstOrNull()
                        ?: throw IllegalStateException("Health Connect kayıt kimliği döndürmedi")
                    val verified = client.readRecord(StepsRecord::class, id).record
                    if (verified.count != delta) {
                        throw IllegalStateException("Adım kaydı doğrulanamadı")
                    }
                    val next = written + delta
                    prefs.edit().putLong(KEY_WRITTEN, next)
                        .putLong(KEY_VERIFIED, next)
                        .putLong(KEY_LAST_END, now).commit()
                    (getSystemService(NOTIFICATION_SERVICE) as NotificationManager)
                        .notify(NOTIFICATION_ID, createNotification(next, target, unlimited))
                }
                if (!unlimited && prefs.getLong(KEY_WRITTEN, 0L) >= target.toLong()) {
                    prefs.edit().putBoolean(KEY_ACTIVE, false).commit()
                    break
                }
                delay(3000L)
            }
        } catch (_: CancellationException) {
            // Durduruldu; önceden eklenen kayıtlar korunur.
        } catch (e: Exception) {
            prefs.edit().putBoolean(KEY_ACTIVE, false).putString(
                KEY_ERROR, e.localizedMessage ?: "Kayıt başarısız").commit()
        } finally {
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
        }
    }

    private fun createNotification(done: Long, target: Int, unlimited: Boolean): Notification {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val stop = PendingIntent.getService(this, 1,
            Intent(this, StepWriterService::class.java).apply { action = ACTION_STOP },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val speed = prefs.getInt(KEY_RATE, 0).toString() +
            if (prefs.getInt(KEY_UNIT, 0) == 1) " adım/sn" else " adım/dk"
        val info = if (unlimited) "$done adım • sınırsız • $speed"
                   else "$done / $target adım • $speed"
        val builder = Notification.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_menu_myplaces)
            .setContentTitle("CamonWalk • adım kayıt testi")
            .setContentText(info).setContentIntent(open)
            .addAction(android.R.drawable.ic_media_pause, "Durdur", stop)
            .setOngoing(true).setOnlyAlertOnce(true)
        if (unlimited) builder.setProgress(0, 0, true)
        else builder.setProgress(target.coerceAtLeast(1), done.coerceAtMost(target.toLong()).toInt(), false)
        return builder.build()
    }

    override fun onDestroy() {
        job?.cancel()
        scope.cancel()
        super.onDestroy()
    }
}
'''
(root / "java/com/camonwalk/app/StepWriterService.kt").write_text(service)

p = root / "java/com/camonwalk/app/MainActivity.kt"
s = p.read_text()
s = s.replace('import android.widget.EditText', '''import android.widget.EditText
import android.widget.Spinner
import android.widget.CheckBox
import android.widget.ArrayAdapter''')
s = s.replace('private lateinit var minutesInput: EditText', '''private lateinit var rateInput: EditText
    private lateinit var unitInput: Spinner
    private lateinit var unlimitedInput: CheckBox''')
s = s.replace('private var pendingMinutes = 0', '''private var pendingRate = 0
    private var pendingUnit = 0
    private var pendingUnlimited = false''')
s = s.replace('if (pendingSteps > 0) requestActivityPermissionOrStart()', 'if (pendingRate > 0) requestActivityPermissionOrStart()')
s = s.replace('minutesInput = findViewById(R.id.minutesInput)', '''rateInput = findViewById(R.id.rateInput)
        unitInput = findViewById(R.id.unitInput)
        unlimitedInput = findViewById(R.id.unlimitedInput)
        unitInput.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item,
            arrayOf("Dakikada adım", "Saniyede adım"))
        unlimitedInput.setOnCheckedChangeListener { _, checked ->
            stepsInput.isEnabled = !checked
            stepsInput.alpha = if (checked) 0.45f else 1.0f
        }''')
start = s.index('        startButton.setOnClickListener {')
end = s.index('        stopButton.setOnClickListener {', start)
s = s[:start] + '''        startButton.setOnClickListener {
            val unlimited = unlimitedInput.isChecked
            val steps = if (unlimited) 0 else stepsInput.text.toString().toIntOrNull()
            val rate = rateInput.text.toString().toIntOrNull()
            val unit = unitInput.selectedItemPosition
            val validRate = if (unit == 1) rate != null && rate in 1..200
                            else rate != null && rate in 1..10000
            if (!validRate || (!unlimited && (steps == null || steps !in 1..2000000000))) {
                toast("Adım hedefi ve hız gir. Hız: 1–200/sn veya 1–10000/dk.")
                return@setOnClickListener
            }
            if (getSharedPreferences(StepWriterService.PREFS, MODE_PRIVATE)
                    .getBoolean(StepWriterService.KEY_ACTIVE, false)) {
                toast("Önce çalışan kaydı durdur")
                return@setOnClickListener
            }
            pendingSteps = steps ?: 0
            pendingRate = rate ?: 0
            pendingUnit = unit
            pendingUnlimited = unlimited
            ensureHealthPermission(true)
        }
''' + s[end:]
start = s.index('    private fun launchWritingService() {')
end = s.index('    private fun verifyHealthEntries() {', start)
s = s[:start] + '''    private fun launchWritingService() {
        if (pendingRate <= 0) return
        val intent = Intent(this, StepWriterService::class.java).apply {
            action = StepWriterService.ACTION_START
            putExtra(StepWriterService.EXTRA_STEPS, pendingSteps)
            putExtra(StepWriterService.EXTRA_RATE, pendingRate)
            putExtra(StepWriterService.EXTRA_UNIT, pendingUnit)
            putExtra(StepWriterService.EXTRA_UNLIMITED, pendingUnlimited)
        }
        try {
            ContextCompat.startForegroundService(this, intent)
            if (Build.VERSION.SDK_INT >= 33 &&
                ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                    != PackageManager.PERMISSION_GRANTED) {
                notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
            toast("Adım kayıt hizmeti başlatılıyor")
        } catch (e: Exception) {
            statusText.text = "Başlatılamadı: " + e.localizedMessage
        } finally {
            pendingSteps = 0
            pendingRate = 0
        }
    }

''' + s[end:]
start = s.index('    private fun refreshProgress() {')
end = s.index('    private fun toast(',start)
s = s[:start] + '''    private fun refreshProgress() {
        val p = getSharedPreferences(StepWriterService.PREFS, MODE_PRIVATE)
        val target = p.getInt(StepWriterService.KEY_TARGET, 0)
        val done = try { p.getLong(StepWriterService.KEY_WRITTEN, 0L) } catch (_: ClassCastException) { p.getInt(StepWriterService.KEY_WRITTEN, 0).toLong() }
        val verified = try { p.getLong(StepWriterService.KEY_VERIFIED, 0L) } catch (_: ClassCastException) { p.getInt(StepWriterService.KEY_VERIFIED, 0).toLong() }
        val active = p.getBoolean(StepWriterService.KEY_ACTIVE, false)
        val unlimited = p.getBoolean(StepWriterService.KEY_UNLIMITED, false)
        val rate = p.getInt(StepWriterService.KEY_RATE, 0)
        val unit = if (p.getInt(StepWriterService.KEY_UNIT, 0) == 1) "sn" else "dk"
        val start = p.getLong(StepWriterService.KEY_START, 0L)
        val elapsed = if (start > 0) ((System.currentTimeMillis()-start).coerceAtLeast(0L)/1000L) else 0L
        val formatter = NumberFormat.getIntegerInstance(Locale("tr", "TR"))
        progressText.text = if (unlimited) formatter.format(done) + " / ∞"
            else formatter.format(done) + " / " + formatter.format(target)
        stepProgress.isIndeterminate = active && unlimited
        if (!unlimited) stepProgress.progress =
            if (target > 0) ((done * 100L) / target).coerceIn(0L,100L).toInt() else 0
        timeText.text = if (start > 0)
            "Çalışma: " + (elapsed / 3600L) + " sa " +
            ((elapsed % 3600L) / 60L) + " dk " + (elapsed % 60L) + " sn"
            else "Çalışma: --"
        val error = p.getString(StepWriterService.KEY_ERROR, "").orEmpty()
        statusText.text = when {
            error.isNotBlank() -> "Hata: " + error
            active -> "Çalışıyor • $rate adım/$unit • $verified adım doğrulandı"
            unlimited && start > 0 -> "Durduruldu • $verified adım doğrulandı"
            target > 0 && done >= target -> "Hedef tamamlandı • $verified adım doğrulandı"
            target > 0 -> "Durduruldu • $verified adım doğrulandı"
            else -> "Hazır • Başlamak için izin ver"
        }
        startButton.isEnabled = !active
        stopButton.isEnabled = active
    }

''' + s[end:]
p.write_text(s)

p = root / "res/layout/activity_main.xml"
s = p.read_text()
s = s.replace('android:text="Adım sayısı"', 'android:text="Toplam adım hedefi"')
start = s.index('            <TextView android:layout_width="match_parent" android:layout_height="wrap_content"\n                android:layout_marginTop="18dp" android:text="Süre (dakika)"')
end = s.index('            <TextView android:layout_width="match_parent" android:layout_height="wrap_content"\n                android:layout_marginTop="14dp" android:text="Senkron modu:',start)
s = s[:start] + '''            <CheckBox android:id="@+id/unlimitedInput"
                android:layout_width="match_parent" android:layout_height="wrap_content"
                android:layout_marginTop="10dp" android:text="Sınırsız çalış (hedef yok)"
                android:buttonTint="@color/mint" android:textColor="@color/white"
                android:textSize="15sp" />
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
                android:layout_marginTop="18dp" android:text="Adım üretim hızı"
                android:textColor="@color/white" android:textSize="15sp"
                android:textStyle="bold" />
            <EditText android:id="@+id/rateInput" android:layout_width="match_parent"
                android:layout_height="54dp" android:layout_marginTop="8dp"
                android:background="@drawable/bg_field" android:inputType="number"
                android:singleLine="true" android:text="120"
                android:textSize="20sp" android:textColor="@color/white"
                android:hint="Hız" android:textColorHint="@color/muted"
                android:paddingLeft="16dp" android:paddingRight="16dp" />
            <Spinner android:id="@+id/unitInput" android:layout_width="match_parent"
                android:layout_height="54dp" android:layout_marginTop="10dp"
                android:background="@drawable/bg_field" android:paddingLeft="16dp"
                android:paddingRight="16dp" />
''' + s[end:]
s=s.replace('android:text="Senkron modu: seçilen süre boyunca adım ve tahmini mesafe kaydı."',
 '''android:text="Seçilen hızla adım ve tahmini mesafe kaydı. Sınırsız modda Durdur'a basana kadar sürer. Android pil yönetimi hizmeti kesebilir."''')
s=s.replace('android:text="Kaydedilen adımlar"','android:text="Kaydedilen adımlar / Hedef"')
p.write_text(s)
