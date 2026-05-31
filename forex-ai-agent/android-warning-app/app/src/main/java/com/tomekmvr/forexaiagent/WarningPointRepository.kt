package com.tomekmvr.forexaiagent

import android.content.Context
import org.json.JSONArray
import org.json.JSONException
import java.io.IOException

class WarningPointRepository(private val context: Context) {
    fun load(): List<WarningPoint> {
        return try {
            val json = context.assets.open("speed_camera_points.json").bufferedReader().use { it.readText() }
            val array = JSONArray(json)
            buildList {
                for (index in 0 until array.length()) {
                    val obj = array.getJSONObject(index)
                    add(
                        WarningPoint(
                            id = obj.getString("id"),
                            name = obj.getString("name"),
                            latitude = obj.getDouble("latitude"),
                            longitude = obj.getDouble("longitude"),
                            speedLimit = if (obj.has("speedLimit")) obj.getInt("speedLimit") else null
                        )
                    )
                }
            }
        } catch (_: IOException) {
            emptyList()
        } catch (_: JSONException) {
            emptyList()
        }
    }
}
