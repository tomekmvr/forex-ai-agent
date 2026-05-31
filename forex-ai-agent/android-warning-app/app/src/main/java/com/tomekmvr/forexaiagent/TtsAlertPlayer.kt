package com.tomekmvr.forexaiagent

import android.content.Context
import android.speech.tts.TextToSpeech
import java.util.Locale

class TtsAlertPlayer(context: Context) : TextToSpeech.OnInitListener {
    private val tts = TextToSpeech(context.applicationContext, this)
    private val pending = ArrayDeque<String>()
    @Volatile
    private var ready = false

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts.language = Locale.US
            ready = true
            while (pending.isNotEmpty()) {
                speakInternal(pending.removeFirst())
            }
        }
    }

    fun speak(text: String) {
        if (ready) {
            speakInternal(text)
        } else {
            if (pending.size >= 5) {
                pending.removeFirst()
            }
            pending.addLast(text)
        }
    }

    fun release() {
        pending.clear()
        tts.stop()
        tts.shutdown()
    }

    private fun speakInternal(text: String) {
        tts.speak(text, TextToSpeech.QUEUE_ADD, null, "alert_${System.currentTimeMillis()}")
    }
}
