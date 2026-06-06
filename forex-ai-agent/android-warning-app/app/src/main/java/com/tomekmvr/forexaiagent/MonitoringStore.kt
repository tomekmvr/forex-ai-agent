package com.tomekmvr.forexaiagent

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class MonitoringSnapshot(
    val monitoringActive: Boolean = false,
    val nearestPoint: WarningPoint? = null,
    val nearestDistanceMeters: Float? = null,
    val lastAlertText: String? = null
)

object MonitoringStore {
    private val mutableState = MutableStateFlow(MonitoringSnapshot())
    val state: StateFlow<MonitoringSnapshot> = mutableState.asStateFlow()

    fun update(snapshot: MonitoringSnapshot) {
        mutableState.value = snapshot
    }
}
