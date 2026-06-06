package pl.fotoradar.speedcamera.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.pm.ServiceInfo
import android.content.Intent
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.os.IBinder
import pl.fotoradar.speedcamera.data.SpeedCameraPoint
import pl.fotoradar.speedcamera.data.SpeedCameraRepository
import pl.fotoradar.speedcamera.engine.AlertEngine
import pl.fotoradar.speedcamera.ui.MainActivity

class LocationMonitoringService : Service() {

    private lateinit var locationManager: LocationManager
    private lateinit var alertEngine: AlertEngine
    private lateinit var repository: SpeedCameraRepository
    private var locationListener: LocationListener? = null

    companion object {
        const val NOTIFICATION_ID = 1001
        const val CHANNEL_ID = "speed_camera_channel"
        const val ACTION_STOP = "pl.fotoradar.speedcamera.STOP"

        var isRunning = false
        var lastLocation: Location? = null
        var nearestCamera: SpeedCameraPoint? = null
        var nearestDistance: Float = Float.MAX_VALUE
        var onStatusUpdate: (() -> Unit)? = null
    }

    override fun onCreate() {
        super.onCreate()
        locationManager = getSystemService(LOCATION_SERVICE) as LocationManager
        alertEngine = AlertEngine(this)
        repository = SpeedCameraRepository(this)

        alertEngine.onNearbyCamera = { camera, distance ->
            if (distance < nearestDistance) {
                nearestCamera = camera
                nearestDistance = distance
                onStatusUpdate?.invoke()
            }
        }

        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopMonitoring()
            stopSelf()
            return START_NOT_STICKY
        }
        startMonitoring()
        return START_STICKY
    }

    private fun startMonitoring() {
        isRunning = true
        nearestCamera = null
        nearestDistance = Float.MAX_VALUE

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(
                NOTIFICATION_ID,
                createNotification("Monitoring aktywny"),
                ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
            )
        } else {
            startForeground(NOTIFICATION_ID, createNotification("Monitoring aktywny"))
        }

        locationListener = LocationListener { location ->
            lastLocation = location
            nearestCamera = null
            nearestDistance = Float.MAX_VALUE

            val nearby = repository.getCamerasNearby(location.latitude, location.longitude, 2000f)
            alertEngine.processLocation(location.latitude, location.longitude, nearby)
            updateNotification()
            onStatusUpdate?.invoke()
        }

        try {
            if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                locationManager.requestLocationUpdates(
                    LocationManager.GPS_PROVIDER, 3000L, 5f, locationListener!!
                )
            }
            if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                locationManager.requestLocationUpdates(
                    LocationManager.NETWORK_PROVIDER, 5000L, 10f, locationListener!!
                )
            }
        } catch (e: SecurityException) {
            stopSelf()
        }
    }

    private fun stopMonitoring() {
        isRunning = false
        locationListener?.let { locationManager.removeUpdates(it) }
        alertEngine.destroy()
    }

    private fun updateNotification() {
        val message = if (nearestCamera != null && nearestDistance < Float.MAX_VALUE) {
            "Fotoradar: ${nearestDistance.toInt()} m"
        } else {
            "Monitoring aktywny – brak fotoradarów w pobliżu"
        }
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIFICATION_ID, createNotification(message))
    }

    private fun createNotification(content: String): Notification {
        val mainIntent = Intent(this, MainActivity::class.java)
        val pi = PendingIntent.getActivity(
            this, 0, mainIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val stopIntent = Intent(this, LocationMonitoringService::class.java).apply { action = ACTION_STOP }
        val stopPi = PendingIntent.getService(
            this, 1, stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("Fotoradary PL")
            .setContentText(content)
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setContentIntent(pi)
            .addAction(Notification.Action.Builder(
                android.graphics.drawable.Icon.createWithResource(this, android.R.drawable.ic_media_pause),
                "Stop", stopPi
            ).build())
            .setOngoing(true)
            .build()
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Monitoring fotoradarów",
            NotificationManager.IMPORTANCE_LOW
        ).apply { description = "Powiadomienia o stanie monitoringu fotoradarów" }
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(channel)
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        super.onDestroy()
        stopMonitoring()
    }
}
