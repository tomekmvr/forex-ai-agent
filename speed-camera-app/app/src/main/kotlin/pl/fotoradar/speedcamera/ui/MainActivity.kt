package pl.fotoradar.speedcamera.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.app.Activity
import android.view.View
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import pl.fotoradar.speedcamera.R
import pl.fotoradar.speedcamera.engine.AlertEngine
import pl.fotoradar.speedcamera.service.LocationMonitoringService

class MainActivity : Activity() {

    private lateinit var btnStartStop: Button
    private lateinit var btnTestAlert: Button
    private lateinit var tvStatus: TextView
    private lateinit var tvNearestCamera: TextView
    private var testAlertEngine: AlertEngine? = null

    private val PERM_REQUEST = 100

    private val requiredPermissions = buildList {
        add(Manifest.permission.ACCESS_FINE_LOCATION)
        add(Manifest.permission.ACCESS_COARSE_LOCATION)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            add(Manifest.permission.POST_NOTIFICATIONS)
        }
    }.toTypedArray()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        btnStartStop = findViewById(R.id.btn_start_stop)
        btnTestAlert = findViewById(R.id.btn_test_alert)
        tvStatus = findViewById(R.id.tv_status)
        tvNearestCamera = findViewById(R.id.tv_nearest_camera)

        btnStartStop.setOnClickListener {
            if (LocationMonitoringService.isRunning) {
                stopMonitoring()
            } else {
                checkPermissionsAndStart()
            }
        }

        btnTestAlert.setOnClickListener {
            if (testAlertEngine == null) testAlertEngine = AlertEngine(this)
            testAlertEngine?.speakTestAlert()
            Toast.makeText(this, "Testowy alert audio odtworzony", Toast.LENGTH_SHORT).show()
        }

        LocationMonitoringService.onStatusUpdate = { runOnUiThread { updateUi() } }
        updateUi()
    }

    private fun checkPermissionsAndStart() {
        val missing = requiredPermissions.filter {
            checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isEmpty()) {
            startMonitoring()
        } else {
            requestPermissions(missing.toTypedArray(), PERM_REQUEST)
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == PERM_REQUEST) {
            if (grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
                startMonitoring()
            } else {
                Toast.makeText(this, "Uprawnienia do lokalizacji są wymagane", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun startMonitoring() {
        val intent = Intent(this, LocationMonitoringService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
        updateUi()
    }

    private fun stopMonitoring() {
        startService(Intent(this, LocationMonitoringService::class.java).apply {
            action = LocationMonitoringService.ACTION_STOP
        })
        updateUi()
    }

    private fun updateUi() {
        val isRunning = LocationMonitoringService.isRunning
        btnStartStop.text = if (isRunning) "■ Zatrzymaj monitoring" else "▶ Rozpocznij monitoring"
        tvStatus.text = if (isRunning) "🟢 Monitoring aktywny" else "🔴 Monitoring nieaktywny"

        val nearest = LocationMonitoringService.nearestCamera
        val dist = LocationMonitoringService.nearestDistance
        if (isRunning && nearest != null && dist < Float.MAX_VALUE) {
            tvNearestCamera.visibility = View.VISIBLE
            val speedInfo = if (nearest.speedLimit != null) " · ${nearest.speedLimit} km/h" else ""
            tvNearestCamera.text = "⚠️ Fotoradar za ${dist.toInt()} m$speedInfo\n${nearest.roadName ?: ""}"
        } else {
            tvNearestCamera.visibility = if (isRunning) View.VISIBLE else View.GONE
            if (isRunning) tvNearestCamera.text = "✅ Brak fotoradarów w pobliżu (zasięg 2 km)"
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        LocationMonitoringService.onStatusUpdate = null
        testAlertEngine?.destroy()
    }
}
