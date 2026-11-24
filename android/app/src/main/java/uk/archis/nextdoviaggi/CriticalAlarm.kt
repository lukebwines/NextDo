package uk.archis.nextdoviaggi

import android.app.*
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.media.RingtoneManager
import android.net.Uri
import android.os.*
import android.view.Gravity
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.PI
import kotlin.math.sin

internal data class AlarmOptions(
    val sound:String="alarm",val custom:String="",val duration:Int=30,val repeat:Int=5,
    val vibrate:Boolean=true,val screen:Boolean=true,val persistent:Boolean=true
)
internal object CriticalAlarm {
    const val CHANNEL="work-critical-alarm-v2"
    const val SERVICE_CHANNEL="work-critical-playback"
    const val TEST="test"
    private val allowed=Regex("[a-f0-9]{64}|test")
    fun valid(key:String)=allowed.matches(key)
    fun options(c:Context):AlarmOptions {
        val p=c.getSharedPreferences("critical_alarm",Context.MODE_PRIVATE)
        return AlarmOptions(
            p.getString("sound","alarm").orEmpty().takeIf{it in listOf("alarm","siren","custom")}?: "alarm",
            p.getString("custom","").orEmpty(),
            p.getInt("duration",30).takeIf{it in listOf(10,30,60)}?:30,
            p.getInt("repeat",5).takeIf{it in listOf(1,5,10,15,30,60)}?:5,
            p.getBoolean("vibrate",true),p.getBoolean("screen",true),p.getBoolean("persistent",true))
    }
    fun save(c:Context,o:AlarmOptions){
        c.getSharedPreferences("critical_alarm",Context.MODE_PRIVATE).edit()
            .putString("sound",o.sound).putString("custom",o.custom)
            .putInt("duration",o.duration).putInt("repeat",o.repeat)
            .putBoolean("vibrate",o.vibrate).putBoolean("screen",o.screen).putBoolean("persistent",o.persistent).apply()
        WorkAlerts.kick(c)
    }
    fun manager(c:Context)=c.getSystemService(NotificationManager::class.java)
    fun fullScreenAllowed(c:Context)=Build.VERSION.SDK_INT<34||manager(c).canUseFullScreenIntent()
    fun exactAllowed(c:Context)=Build.VERSION.SDK_INT<31||c.getSystemService(AlarmManager::class.java).canScheduleExactAlarms()
    fun channelAllowed(c:Context):Boolean {
        val ch=manager(c).getNotificationChannel(CHANNEL)
        return WorkAlerts.permission(c)&&ch!=null&&ch.importance>=NotificationManager.IMPORTANCE_DEFAULT
    }
    fun alarmIntent(c:Context,key:String):PendingIntent=PendingIntent.getActivity(c,7101,
        Intent(c,CriticalAlarmActivity::class.java).setData(Uri.parse("nextdo-alarm://open/"+key))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    fun action(c:Context,key:String,action:String):PendingIntent=PendingIntent.getBroadcast(c,7102,
        Intent(c,WorkAlertReceiver::class.java).setAction(action).setData(Uri.parse("nextdo-alarm://action/"+key)),
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    fun launch(c:Context,key:String){
        if(!valid(key)||!channelAllowed(c))return
        // Android may deny background FGS startup. The audible notification is the fallback.
        try{ContextCompat.startForegroundService(c,Intent(c,CriticalAlarmService::class.java).putExtra("key",key))}
        catch(_:Exception){}
    }
    fun stop(c:Context,key:String?=null){
        val instance=CriticalAlarmService.current
        if(instance!=null)instance.halt(key)
        else if(key==null)c.stopService(Intent(c,CriticalAlarmService::class.java))
    }
    fun finishTest(c:Context){
        stop(c,TEST);manager(c).cancel("nextdo-work-alert:test",7001)
    }
    fun sound(c:Context,o:AlarmOptions):Uri {
        if(o.sound=="custom"&&o.custom.isNotBlank()){
            val uri=Uri.parse(o.custom)
            if(uri.scheme=="content")return uri
        }
        return RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
    }
    // Original alternating two-tone waveform, no downloaded audio or additional permission.
    fun siren(c:Context):File {
        val f=File(c.cacheDir,"nextdo-critical-siren.wav")
        if(f.length()==64044L)return f
        val n=32000;val rate=16000
        val b=ByteBuffer.allocate(44+n*2).order(ByteOrder.LITTLE_ENDIAN)
        b.put("RIFF".toByteArray()).putInt(36+n*2).put("WAVEfmt ".toByteArray()).putInt(16)
        b.putShort(1).putShort(1).putInt(rate).putInt(rate*2).putShort(2).putShort(16)
        b.put("data".toByteArray()).putInt(n*2)
        for(i in 0 until n){
            val part=i%8000;val hz=if((i/8000)%2==0)740.0 else 1040.0
            val edge=minOf(1.0,part/300.0,(7999-part)/300.0)
            b.putShort((sin(2*PI*hz*part/rate)*9000*edge).toInt().toShort())
        }
        f.writeBytes(b.array());return f
    }
}
class CriticalAlarmService:Service(){
    companion object {@Volatile internal var current:CriticalAlarmService?=null}
    private val handler=Handler(Looper.getMainLooper())
    private var playing:String?=null
    private var player:MediaPlayer?=null
    private var audio:AudioManager?=null
    private var focus:AudioFocusRequest?=null
    private var vibrator:Vibrator?=null
    private val finish=Runnable{end()}
    private val attr=AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM)
        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build()
    override fun onCreate(){super.onCreate();current=this}
    override fun onBind(intent:Intent?)=null
    override fun onStartCommand(intent:Intent?,flags:Int,startId:Int):Int {
        val key=intent?.getStringExtra("key")?: ""
        if(playing!=null)return START_NOT_STICKY
        try{
            val open=CriticalAlarm.alarmIntent(this,key)
            val notification=NotificationCompat.Builder(this,CriticalAlarm.SERVICE_CHANNEL)
                .setSmallIcon(android.R.drawable.ic_dialog_alert).setContentTitle("NextDo · Allarme in corso")
                .setContentText("Suono temporaneo · tocca per gestire").setContentIntent(open)
                .addAction(0,"Silenzia",CriticalAlarm.action(this,key,"uk.archis.nextdo.ALERT_SILENCE"))
                .setOngoing(true).setSilent(true).setVisibility(NotificationCompat.VISIBILITY_PRIVATE).build()
            startForeground(7103,notification)
            if(!CriticalAlarm.valid(key)||!WorkAlerts.alarmActive(this,key)||!CriticalAlarm.channelAllowed(this)){
                end();return START_NOT_STICKY
            }
            val manager=CriticalAlarm.manager(this)
            // Respect OS channel mute, vibration and DND. Never change device volume or DND.
            val channel=manager.getNotificationChannel(CriticalAlarm.CHANNEL)
            if(manager.currentInterruptionFilter !in listOf(NotificationManager.INTERRUPTION_FILTER_ALL,NotificationManager.INTERRUPTION_FILTER_ALARMS)){
                end();return START_NOT_STICKY
            }
            playing=key
            val o=CriticalAlarm.options(this)
            handler.postDelayed(finish,o.duration*1000L)
            if(channel?.sound!=null){
                val am=getSystemService(AudioManager::class.java);audio=am
                val request=AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
                    .setAudioAttributes(attr).setOnAudioFocusChangeListener { change ->
                        if(change==AudioManager.AUDIOFOCUS_LOSS||change==AudioManager.AUDIOFOCUS_LOSS_TRANSIENT)handler.post{end()}
                    }.build()
                if(am.requestAudioFocus(request)==AudioManager.AUDIOFOCUS_REQUEST_GRANTED){
                    focus=request
                    val mp=MediaPlayer();player=mp;mp.setAudioAttributes(attr)
                    try{
                        if(o.sound=="siren")mp.setDataSource(CriticalAlarm.siren(this).absolutePath)
                        else mp.setDataSource(this,CriticalAlarm.sound(this,o))
                    }catch(_:Exception){
                        mp.reset();mp.setAudioAttributes(attr)
                        mp.setDataSource(this,RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM))
                    }
                    mp.isLooping=true
                    mp.setOnPreparedListener { if(playing==key&&player===it)it.start() }
                    mp.setOnErrorListener { _,_,_->end();true }
                    mp.prepareAsync()
                }
            }
            if(o.vibrate&&channel?.shouldVibrate()==true){
                @Suppress("DEPRECATION")
                val v=if(Build.VERSION.SDK_INT>=31)getSystemService(VibratorManager::class.java).defaultVibrator else getSystemService(Vibrator::class.java)
                vibrator=v
                if(v.hasVibrator())v.vibrate(VibrationEffect.createWaveform(longArrayOf(0,500,250,500,900),0),attr)
            }
        }catch(_:Exception){end()}
        return START_NOT_STICKY
    }
    internal fun halt(key:String?){handler.post{if(key==null||playing==key)end()}}
    private fun release(){
        handler.removeCallbacks(finish)
        try{player?.release()}catch(_:Exception){};player=null
        try{vibrator?.cancel()}catch(_:Exception){};vibrator=null
        try{focus?.let{audio?.abandonAudioFocusRequest(it)}}catch(_:Exception){};focus=null;audio=null
        playing=null
    }
    private fun end(){release();stopForeground(STOP_FOREGROUND_REMOVE);stopSelf()}
    override fun onDestroy(){release();if(current===this)current=null;super.onDestroy()}
}
class CriticalAlarmActivity:Activity(){
    private val handler=Handler(Looper.getMainLooper())
    private var key=""
    private val monitor=object:Runnable{
        override fun run(){
            if(!WorkAlerts.alarmActive(this@CriticalAlarmActivity,key)){finish();return}
            handler.postDelayed(this,1000)
        }
    }
    override fun onCreate(state:Bundle?){
        super.onCreate(state)
        key=intent.data?.lastPathSegment.orEmpty()
        if(!CriticalAlarm.valid(key)||!WorkAlerts.alarmActive(this,key)){finish();return}
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        if(CriticalAlarm.options(this).screen){setShowWhenLocked(true);setTurnScreenOn(true)}
        val layout=LinearLayout(this).apply{
            orientation=LinearLayout.VERTICAL;gravity=Gravity.CENTER;setPadding(40,40,40,40)
            setBackgroundColor(Color.rgb(18,24,32))
        }
        fun label(text:String,size:Float,color:Int){layout.addView(TextView(this).apply{
            this.text=text;textSize=size;setTextColor(color);gravity=Gravity.CENTER;setPadding(0,18,0,18)
        })}
        fun button(text:String,click:()->Unit){layout.addView(Button(this).apply{
            this.text=text;setOnClickListener{click()}
        },LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT,LinearLayout.LayoutParams.WRAP_CONTENT))}
        label("NextDo · Professionale",18f,Color.LTGRAY)
        label(if(key==CriticalAlarm.TEST)"PROVA ALLARME" else "AVVISO CRITICO",32f,Color.rgb(255,100,100))
        label(if(key==CriticalAlarm.TEST)"Nessuna scadenza reale." else "È richiesta la tua attenzione.",20f,Color.WHITE)
        button(if(key==CriticalAlarm.TEST)"Termina prova" else "Presa visione"){
            if(key==CriticalAlarm.TEST){CriticalAlarm.finishTest(this);finish()}
            else unlockAndAcknowledge()
        }
        button("Silenzia questo suono"){
            CriticalAlarm.stop(this,key)
            if(key==CriticalAlarm.TEST)CriticalAlarm.finishTest(this)
            finish()
        }
        button("Apri NextDo"){startActivity(Intent(this,MainActivity::class.java));finish()}
        setContentView(layout)
        handler.post(monitor)
    }
    private fun unlockAndAcknowledge(){
        val km=getSystemService(KeyguardManager::class.java)
        if(km.isKeyguardLocked)km.requestDismissKeyguard(this,object:KeyguardManager.KeyguardDismissCallback(){
            override fun onDismissSucceeded(){ack()}
        })else ack()
    }
    private fun ack(){
        val k=key
        CriticalAlarm.stop(this,k)
        Thread{WorkAlerts.acknowledge(applicationContext,k)}.start()
        finish()
    }
    override fun onDestroy(){handler.removeCallbacks(monitor);super.onDestroy()}
}
