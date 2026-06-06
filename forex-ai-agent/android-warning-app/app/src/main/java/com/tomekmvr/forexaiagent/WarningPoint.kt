package com.tomekmvr.forexaiagent

data class WarningPoint(
    val id: String,
    val name: String,
    val latitude: Double,
    val longitude: Double,
    val speedLimit: Int?
)
