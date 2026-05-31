package com.tomekmvr.forexaiagent

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.IBinder
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority

class MonitoringService : Service() {
    private lateinit var fusedLocationClient: FusedLocationProviderClient
    private lateinit var warningPoints: List<WarningPoint>
    private lateinit var ttsAlertPlayer: TtsAlertPlayer
    private val alertEngine = AlertEngine()
    private var isMonitoring = false

    private val locationCallback = object : LocationCallback() {
        override fun onLocationResult(locationResult: LocationResult) {
            val location = locationResult.lastLocation ?: return
            val nearest = DistanceUtils.findNearest(location.latitude, location.longitude, warningPoints)
            if (nearest == null) {
                MonitoringStore.update(MonitoringSnapshot(monitoringActive = true))
                return
            }

            val (point, distance) = nearest
            val alert = alertEngine.onNearest(point, distance)
            if (alert != null) {
                ttsAlertPlayer.speak(alert)
            }

            MonitoringStore.update(
                MonitoringSnapshot(
                    monitoringActive = true,
                    nearestPoint = point,
                    nearestDistanceMeters = distance,
                    lastAlertText = alert ?: MonitoringStore.state.value.lastAlertText
                )
            )
        }
    }

    override fun onCreate() {
        super.onCreate()
        fusedLocationClient = LocationServices.getFusedLocationProviderClient(this)
        warningPoints = WarningPointRepository(this).load()
        ttsAlertPlayer = TtsAlertPlayer(this)
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopMonitoring()
                stopSelf()
                return START_NOT_STICKY
            }
            else -> startMonitoring()
        }
        return START_STICKY
    }

    private fun startMonitoring() {
        if (isMonitoring) return
        if (!hasLocationPermission()) {
            MonitoringStore.update(MonitoringSnapshot(monitoringActive = false))
            stopSelf()
            return
        }

        startForeground(NOTIFICATION_ID, buildNotification())
        MonitoringStore.update(MonitoringStore.state.value.copy(monitoringActive = true))

        val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 4000L)
            .setMinUpdateIntervalMillis(2000L)
            .build()

        fusedLocationClient.requestLocationUpdates(request, locationCallback, mainLooper)
        isMonitoring = true
    }

    private fun stopMonitoring() {
        if (!isMonitoring) return
        fusedLocationClient.removeLocationUpdates(locationCallback)
        ttsAlertPlayer.release()
        MonitoringStore.update(MonitoringSnapshot(monitoringActive = false))
        stopForeground(STOP_FOREGROUND_REMOVE)
        isMonitoring = false
    }

    private fun hasLocationPermission(): Boolean {
        return ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
            ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
    }

    private fun buildNotification(): Notification {
        val openIntent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            openIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(getString(R.string.notification_text))
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.channel_name),
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = getString(R.string.channel_description)
            }
            val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(channel)
        }
    }

    override fun onDestroy() {
        if (isMonitoring) {
            fusedLocationClient.removeLocationUpdates(locationCallback)
        }
        ttsAlertPlayer.release()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        const val ACTION_START = "com.tomekmvr.forexaiagent.action.START"
        const val ACTION_STOP = "com.tomekmvr.forexaiagent.action.STOP"
        private const val CHANNEL_ID = "speed_camera_monitor"
        private const val NOTIFICATION_ID = 1001

        fun start(context: Context) {
            val intent = Intent(context, MonitoringService::class.java).setAction(ACTION_START)
            androidx.core.content.ContextCompat.startForegroundService(context, intent)
        }

        fun stop(context: Context) {
            val intent = Intent(context, MonitoringService::class.java).setAction(ACTION_STOP)
            context.startService(intent)
        }
    }
}
