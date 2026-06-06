package pl.fotoradar.speedcamera.data

import android.content.Context
import org.json.JSONArray

class SpeedCameraRepository(private val context: Context) {

    private var cameras: List<SpeedCameraPoint> = emptyList()

    fun loadCameras(): List<SpeedCameraPoint> {
        if (cameras.isNotEmpty()) return cameras

        return try {
            val json = context.assets.open("speed_cameras.json")
                .bufferedReader()
                .use { it.readText() }
            val arr = JSONArray(json)
            val result = mutableListOf<SpeedCameraPoint>()
            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                result.add(
                    SpeedCameraPoint(
                        id = obj.getString("id"),
                        latitude = obj.getDouble("latitude"),
                        longitude = obj.getDouble("longitude"),
                        type = obj.getString("type"),
                        speedLimit = if (obj.isNull("speedLimit")) null else obj.getInt("speedLimit"),
                        roadName = if (obj.isNull("roadName")) null else obj.getString("roadName"),
                        direction = if (obj.isNull("direction")) null else obj.getString("direction")
                    )
                )
            }
            cameras = result
            cameras
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun getCamerasNearby(
        latitude: Double,
        longitude: Double,
        radiusMeters: Float = 2000f
    ): List<Pair<SpeedCameraPoint, Float>> {
        val allCameras = loadCameras()
        val results = mutableListOf<Pair<SpeedCameraPoint, Float>>()

        for (camera in allCameras) {
            val distance = calculateDistance(latitude, longitude, camera.latitude, camera.longitude)
            if (distance <= radiusMeters) {
                results.add(Pair(camera, distance))
            }
        }

        return results.sortedBy { it.second }
    }

    private fun calculateDistance(
        lat1: Double, lon1: Double,
        lat2: Double, lon2: Double
    ): Float {
        val earthRadius = 6371000f
        val dLat = Math.toRadians(lat2 - lat1)
        val dLon = Math.toRadians(lon2 - lon1)
        val a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2)) *
                Math.sin(dLon / 2) * Math.sin(dLon / 2)
        val c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
        return (earthRadius * c).toFloat()
    }
}
