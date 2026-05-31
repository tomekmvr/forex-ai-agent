package com.tomekmvr.forexaiagent

class AlertEngine {
    private val thresholds = listOf(1000, 500, 200)
    private val triggeredThresholds = mutableMapOf<String, MutableSet<Int>>()

    fun onNearest(point: WarningPoint, distanceMeters: Float): String? {
        val distanceInt = distanceMeters.toInt()
        val threshold = thresholds.firstOrNull { distanceInt <= it && !alreadyTriggered(point.id, it) } ?: return null
        markTriggered(point.id, threshold)
        return if (point.speedLimit != null) {
            "Warning. Speed camera in $threshold meters. Limit ${point.speedLimit} kilometers per hour."
        } else {
            "Warning. Speed camera in $threshold meters."
        }
    }

    private fun alreadyTriggered(pointId: String, threshold: Int): Boolean {
        return triggeredThresholds[pointId]?.contains(threshold) == true
    }

    private fun markTriggered(pointId: String, threshold: Int) {
        val bucket = triggeredThresholds.getOrPut(pointId) { mutableSetOf() }
        bucket.add(threshold)
    }
}
