package com.tomekmvr.forexaiagent

import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AlertEngineTest {
    @Test
    fun triggersThresholdsOncePerPoint() {
        val engine = AlertEngine()
        val point = WarningPoint("id-1", "Test", 0.0, 0.0, 50)

        val first = engine.onNearest(point, 950f)
        val repeated = engine.onNearest(point, 900f)

        assertTrue(first?.contains("1000") == true)
        assertNull(repeated)
    }
}
