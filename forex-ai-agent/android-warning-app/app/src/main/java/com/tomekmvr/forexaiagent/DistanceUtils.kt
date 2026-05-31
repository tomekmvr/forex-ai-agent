package com.tomekmvr.forexaiagent

import android.location.Location

object DistanceUtils {
    fun findNearest(lat: Double, lon: Double, points: List<WarningPoint>): Pair<WarningPoint, Float>? {
        var nearestPoint: WarningPoint? = null
        var nearestDistance = Float.MAX_VALUE
        val buffer = FloatArray(1)
        for (point in points) {
            Location.distanceBetween(lat, lon, point.latitude, point.longitude, buffer)
            val currentDistance = buffer[0]
            if (currentDistance < nearestDistance) {
                nearestDistance = currentDistance
                nearestPoint = point
            }
        }
        return if (nearestPoint == null) null else nearestPoint to nearestDistance
    }
}
