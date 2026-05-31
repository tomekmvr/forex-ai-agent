package pl.fotoradar.speedcamera.data

data class SpeedCameraPoint(
    val id: String,
    val latitude: Double,
    val longitude: Double,
    val type: String,
    val speedLimit: Int?,
    val roadName: String?,
    val direction: String?
)
