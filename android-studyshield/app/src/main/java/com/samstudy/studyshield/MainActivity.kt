package com.samstudy.studyshield

import android.app.Activity
import android.app.AppOpsManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

class MainActivity : Activity() {
    private val prefs by lazy { getSharedPreferences("shield", MODE_PRIVATE) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        render()
    }

    private fun render() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(28, 40, 28, 28)
        }
        root.addView(TextView(this).apply {
            text = "SamStudy StudyShield"
            textSize = 28f
            gravity = Gravity.CENTER
        })
        root.addView(TextView(this).apply {
            text = "\nSet an individual daily limit for launchable apps. Accessibility + Usage Access are required for enforcement."
            textSize = 16f
        })

        root.addView(Button(this).apply {
            text = "Open Accessibility Settings"
            setOnClickListener { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        })
        root.addView(Button(this).apply {
            text = "Open Usage Access Settings"
            setOnClickListener { startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)) }
        })

        val appsBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(TextView(this).apply { text = "\nApps"; textSize = 22f })

        val apps = packageManager.queryIntentActivities(
            Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER),
            PackageManager.MATCH_ALL
        ).map { it.activityInfo.packageName to (it.loadLabel(packageManager)?.toString() ?: it.activityInfo.packageName) }
            .filter { it.first != packageName }
            .distinctBy { it.first }
            .sortedBy { it.second.lowercase() }

        apps.forEach { (pkg, label) ->
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                setPadding(0, 10, 0, 10)
            }
            val title = TextView(this).apply {
                text = label
                textSize = 16f
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            }
            val input = EditText(this).apply {
                hint = "min/day"
                inputType = 2
                val old = prefs.getLong("limit_$pkg", -1L)
                if (old > 0) setText(old.toString())
                layoutParams = LinearLayout.LayoutParams(150, LinearLayout.LayoutParams.WRAP_CONTENT)
            }
            val save = Button(this).apply {
                text = "Save"
                setOnClickListener {
                    val mins = input.text.toString().toLongOrNull() ?: 0L
                    if (mins <= 0) prefs.edit().remove("limit_$pkg").apply()
                    else prefs.edit().putLong("limit_$pkg", mins).apply()
                    render()
                }
            }
            row.addView(title); row.addView(input); row.addView(save)
            appsBox.addView(row)
        }

        val scroll = ScrollView(this).apply { addView(appsBox) }
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        root.addView(TextView(this).apply {
            text = "\nNote: Android does not allow an ordinary app to guarantee that a user cannot uninstall or force-stop it. StudyShield can enforce limits while its Accessibility service is enabled."
            textSize = 13f
        })
        setContentView(root)
    }
}
