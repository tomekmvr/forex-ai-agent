package com.tomekmvr.forexaiagent

import android.content.Intent
import android.content.pm.ApplicationInfo
import androidx.car.app.CarAppService
import androidx.car.app.Session
import androidx.car.app.Screen
import androidx.car.app.model.Action
import androidx.car.app.model.ActionStrip
import androidx.car.app.model.CarText
import androidx.car.app.model.ItemList
import androidx.car.app.model.ListTemplate
import androidx.car.app.model.Row
import androidx.car.app.validation.HostValidator

class SpeedCamCarAppService : CarAppService() {
    override fun onCreateSession(): Session = SpeedCamSession()

    override fun createHostValidator(): HostValidator {
        val isDebuggable = applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE != 0
        return if (isDebuggable) {
            HostValidator.ALLOW_ALL_HOSTS_VALIDATOR
        } else {
            HostValidator.Builder(this).build()
        }
    }
}

class SpeedCamSession : Session() {
    override fun onCreateScreen(intent: Intent): Screen = SpeedCamStatusScreen(carContext)
}

class SpeedCamStatusScreen(carContext: androidx.car.app.CarContext) : Screen(carContext) {
    override fun onGetTemplate(): androidx.car.app.model.Template {
        val snapshot = MonitoringStore.state.value
        val rows = ItemList.Builder()
            .addItem(Row.Builder().setTitle(if (snapshot.monitoringActive) "Monitoring active" else "Monitoring stopped").build())

        val nearest = snapshot.nearestPoint
        if (nearest != null && snapshot.nearestDistanceMeters != null) {
            rows.addItem(
                Row.Builder()
                    .setTitle("Nearest point")
                    .addText(CarText.create("${nearest.name} (${snapshot.nearestDistanceMeters.toInt()} m)"))
                    .addText(CarText.create(nearest.speedLimit?.let { "Limit: $it km/h" } ?: "Speed limit unavailable"))
                    .build()
            )
        } else {
            rows.addItem(Row.Builder().setTitle("Nearest point").addText(CarText.create("No data")).build())
        }

        if (snapshot.lastAlertText != null) {
            rows.addItem(Row.Builder().setTitle("Last alert").addText(CarText.create(snapshot.lastAlertText)).build())
        }

        return ListTemplate.Builder()
            .setSingleList(rows.build())
            .setTitle("Speed camera monitor")
            .setHeaderAction(Action.APP_ICON)
            .setActionStrip(
                ActionStrip.Builder()
                    .addAction(
                        Action.Builder()
                            .setTitle("Refresh")
                            .setOnClickListener { invalidate() }
                            .build()
                    )
                    .build()
            )
            .build()
    }
}
