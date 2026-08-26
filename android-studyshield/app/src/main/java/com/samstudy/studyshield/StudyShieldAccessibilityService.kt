package com.samstudy.studyshield

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.app.usage.UsageStatsManager
import android.content.Intent
import android.os.SystemClock
import android.view.accessibility.AccessibilityEvent

class StudyShieldAccessibilityService : AccessibilityService() {
    override fun onServiceConnected() {
        serviceInfo = AccessibilityServiceInfo().apply {
            eventTypes = AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED or AccessibilityEvent.TYPE_WINDOWS_CHANGED
            feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC
            notificationTimeout = 100
        }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        val pkg = event?.packageName?.toString() ?: return
        if (pkg == packageName || pkg.startsWith("com.android.systemui")) return
        val prefs = getSharedPreferences("shield", MODE_PRIVATE)
        val limit = prefs.getLong("limit_$pkg", -1L)
        if (limit <= 0L) return

        val now = System.currentTimeMillis()
        val startOfDay = now - (now % 86_400_000L)
        val usm = getSystemService(USAGE_STATS_SERVICE) as UsageStatsManager
        val stats = usm.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, startOfDay, now)
        val used = stats.firstOrNull { it.packageName == pkg }?.totalTimeInForeground ?: 0L
        if (used >= limit * 60_000L) {
            startActivity(Intent(this, LockActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS)
                putExtra("app", pkg)
                putExtra("minutes", limit)
            })
        }
    }

    override fun onInterrupt() {}
}
