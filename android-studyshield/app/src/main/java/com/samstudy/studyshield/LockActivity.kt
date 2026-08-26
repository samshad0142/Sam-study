package com.samstudy.studyshield

import android.app.Activity
import android.os.Bundle
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.TextView

class LockActivity : Activity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    val app=intent.getStringExtra("app") ?: "this app"
    val mins=intent.getLongExtra("minutes",0L)
    val box=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; gravity=Gravity.CENTER; setPadding(32,32,32,32) }
    box.addView(TextView(this).apply { text="StudyShield active"; textSize=28f; gravity=Gravity.CENTER })
    box.addView(TextView(this).apply { text="\nDaily limit reached for:\n$app\n\nAllowed: $mins minutes/day\nCome back tomorrow to use it again."; textSize=18f; gravity=Gravity.CENTER })
    setContentView(box)
  }
  override fun onBackPressed() { /* keep lock screen simple */ }
}
