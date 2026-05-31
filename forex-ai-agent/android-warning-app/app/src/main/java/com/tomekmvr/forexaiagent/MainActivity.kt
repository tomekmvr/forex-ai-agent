package com.tomekmvr.forexaiagent

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {
    private lateinit var statusText: TextView
    private lateinit var nearestText: TextView
    private lateinit var lastAlertText: TextView

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) {
        if (hasRequiredPermissions()) {
            MonitoringService.start(this)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        statusText = findViewById(R.id.statusText)
        nearestText = findViewById(R.id.nearestText)
        lastAlertText = findViewById(R.id.lastAlertText)

        findViewById<Button>(R.id.startButton).setOnClickListener {
            if (hasRequiredPermissions()) {
                MonitoringService.start(this)
            } else {
                requestPermissions()
            }
        }

        findViewById<Button>(R.id.stopButton).setOnClickListener {
            MonitoringService.stop(this)
        }

        lifecycleScope.launch {
            MonitoringStore.state.collectLatest { snapshot ->
                statusText.text = if (snapshot.monitoringActive) getString(R.string.status_active) else getString(R.string.status_stopped)
                val nearest = snapshot.nearestPoint
                nearestText.text = if (nearest == null || snapshot.nearestDistanceMeters == null) {
                    getString(R.string.no_nearest)
                } else {
                    val distance = snapshot.nearestDistanceMeters.toInt()
                    val limit = nearest.speedLimit?.let { " (${it} km/h)" } ?: ""
                    "Nearest point: ${nearest.name} - ${distance} m$limit"
                }
                lastAlertText.text = snapshot.lastAlertText?.let { "Last alert: $it" } ?: getString(R.string.no_alert)
            }
        }
    }

    private fun hasRequiredPermissions(): Boolean {
        val locationGranted = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED

        val notificationsGranted =
            Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
                ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

        return locationGranted && notificationsGranted
    }

    private fun requestPermissions() {
        val permissions = mutableListOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions += Manifest.permission.POST_NOTIFICATIONS
        }
        permissionLauncher.launch(permissions.toTypedArray())
    }
}
