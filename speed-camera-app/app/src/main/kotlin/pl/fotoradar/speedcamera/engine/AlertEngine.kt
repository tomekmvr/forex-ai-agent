package pl.fotoradar.speedcamera.engine

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import pl.fotoradar.speedcamera.data.SpeedCameraPoint
import java.util.Locale

data class AlertState(
    val pointId: String,
    val alerted1000: Boolean = false,
    val alerted500: Boolean = false,
    val alerted200: Boolean = false,
    val lastAlertTimestamp: Long = 0L
)

class AlertEngine(private val context: Context) : TextToSpeech.OnInitListener {

    private var tts: TextToSpeech? = null
    private var isTtsReady = false
    private val alertStates = mutableMapOf<String, AlertState>()
    private val handler = Handler(Looper.getMainLooper())

    var onNearbyCamera: ((SpeedCameraPoint, Float) -> Unit)? = null

    companion object {
        const val THRESHOLD_1000 = 1000f
        const val THRESHOLD_500 = 500f
        const val THRESHOLD_200 = 200f
        const val COOLDOWN_MS = 15_000L
        const val CLEANUP_RADIUS = 3000f
    }

    init {
        tts = TextToSpeech(context, this)
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts?.language = Locale("pl", "PL")
            isTtsReady = true
        }
    }

    fun processLocation(
        latitude: Double,
        longitude: Double,
        nearbyCameras: List<Pair<SpeedCameraPoint, Float>>
    ) {
        val now = System.currentTimeMillis()

        for ((camera, distance) in nearbyCameras) {
            val state = alertStates.getOrPut(camera.id) { AlertState(camera.id) }
            onNearbyCamera?.invoke(camera, distance)

            when {
                distance <= THRESHOLD_200 && !state.alerted200 -> {
                    if (now - state.lastAlertTimestamp >= COOLDOWN_MS) {
                        speakAlert(camera, 200)
                        alertStates[camera.id] = state.copy(
                            alerted200 = true,
                            alerted500 = true,
                            alerted1000 = true,
                            lastAlertTimestamp = now
                        )
                    }
                }
                distance <= THRESHOLD_500 && !state.alerted500 -> {
                    if (now - state.lastAlertTimestamp >= COOLDOWN_MS) {
                        speakAlert(camera, 500)
                        alertStates[camera.id] = state.copy(
                            alerted500 = true,
                            alerted1000 = true,
                            lastAlertTimestamp = now
                        )
                    }
                }
                distance <= THRESHOLD_1000 && !state.alerted1000 -> {
                    if (now - state.lastAlertTimestamp >= COOLDOWN_MS) {
                        speakAlert(camera, 1000)
                        alertStates[camera.id] = state.copy(
                            alerted1000 = true,
                            lastAlertTimestamp = now
                        )
                    }
                }
            }
        }

        cleanupDistantCameras(nearbyCameras)
    }

    private fun speakAlert(camera: SpeedCameraPoint, distanceMeters: Int) {
        if (!isTtsReady) return

        val speedInfo = if (camera.speedLimit != null) {
            ", ograniczenie ${camera.speedLimit} km/h"
        } else {
            ""
        }
        val text = "Uwaga, fotoradar za $distanceMeters metrów$speedInfo"

        handler.post {
            tts?.speak(text, TextToSpeech.QUEUE_ADD, null, "alert_${camera.id}_$distanceMeters")
        }
    }

    fun speakTestAlert() {
        if (!isTtsReady) return
        val text = "Test alertu. Fotoradar za 500 metrów, ograniczenie 50 kilometrów na godzinę"
        handler.post {
            tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "test_alert")
        }
    }

    private fun cleanupDistantCameras(nearbyCameras: List<Pair<SpeedCameraPoint, Float>>) {
        val nearbyIds = nearbyCameras
            .filter { it.second < CLEANUP_RADIUS }
            .map { it.first.id }
            .toSet()

        val idsToRemove = alertStates.keys.filter { it !in nearbyIds }
        idsToRemove.forEach { alertStates.remove(it) }
    }

    fun destroy() {
        tts?.stop()
        tts?.shutdown()
    }
}
