package com.tomekmvr.forexaiagent

import android.content.Context
import android.speech.tts.TextToSpeech
import java.util.Locale

class TtsAlertPlayer(context: Context) : TextToSpeech.OnInitListener {
    private val tts = TextToSpeech(context.applicationContext, this)
    @Volatile
    private var ready = false

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts.language = Locale.US
            ready = true
        }
    }

    fun speak(text: String) {
        if (ready) {
            tts.speak(text, TextToSpeech.QUEUE_ADD, null, "alert_${System.currentTimeMillis()}")
        }
    }

    fun release() {
        tts.stop()
        tts.shutdown()
    }
}
