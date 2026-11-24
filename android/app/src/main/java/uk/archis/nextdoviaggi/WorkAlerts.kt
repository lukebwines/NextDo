package uk.archis.nextdoviaggi

import android.Manifest
import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.*
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * No agenda bearer token in background. Only opaque identifiers, priority and reminder times.
 * The separate vault key does not require biometric authentication, specifically for this opt-in scope.
 */
internal object WorkAlerts {
    private val lock=Any()
    private val runLock=Any()
    private const val periodic="nextdo-work-alert-periodic"
    private const val immediate="nextdo-work-alert-now"
    private const val tag="nextdo-work-alert:"
    private const val id=7001
    private const val day=86400L
    private val keyPattern=Regex("[a-f0-9]{64}")
    private fun now()=System.currentTimeMillis()/1000
    private fun manager(c:Context)=c.getSystemService(NotificationManager::class.java)
    private fun vault(c:Context)=Vault(c,true)
    private fun read(c:Context,name:String):JSONObject? {
        val v=vault(c)
        return if(v.exists(name))JSONObject(String(v.read(name),Charsets.UTF_8)) else null
    }
    private fun write(c:Context,name:String,data:JSONObject)=vault(c).write(name,data.toString().toByteArray(Charsets.UTF_8))
    fun matches(c:Context,token:String)=synchronized(lock){try{read(c,"config")?.str("token")==token}catch(_:Exception){false}}
    fun enabled(c:Context)=synchronized(lock){vault(c).exists("config")}
    fun interval(c:Context)=CriticalAlarm.options(c).repeat
    fun permission(c:Context)= (Build.VERSION.SDK_INT<33||ContextCompat.checkSelfPermission(c,Manifest.permission.POST_NOTIFICATIONS)==PackageManager.PERMISSION_GRANTED)&&NotificationManagerCompat.from(c).areNotificationsEnabled()
    fun channels(c:Context){
        val sound=RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
        val alarm=RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
        val attr=AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_NOTIFICATION).build()
        val ids=listOf("work-low" to NotificationManager.IMPORTANCE_LOW,"work-normal" to NotificationManager.IMPORTANCE_DEFAULT,"work-high" to NotificationManager.IMPORTANCE_HIGH,CriticalAlarm.CHANNEL to NotificationManager.IMPORTANCE_HIGH,CriticalAlarm.SERVICE_CHANNEL to NotificationManager.IMPORTANCE_LOW)
        for((channel,importance) in ids){
            val label=when(channel){"work-low"->"Professionale · Silenziose";"work-normal"->"Professionale · Normali";"work-high"->"Professionale · Alta priorità";CriticalAlarm.CHANNEL->"Professionale · Allarmi critici";else->"Professionale · Allarme in corso"}
            val ch=NotificationChannel(channel,label,importance)
            ch.lockscreenVisibility=android.app.Notification.VISIBILITY_PRIVATE
            when(channel){
                "work-low",CriticalAlarm.SERVICE_CHANNEL->{ch.setSound(null,null);ch.enableVibration(false)}
                CriticalAlarm.CHANNEL->{ch.setSound(alarm,AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).build());ch.enableVibration(true);ch.vibrationPattern=longArrayOf(0,600,250,600,250,1000)}
                "work-high"->{ch.setSound(sound,attr);ch.enableVibration(true);ch.vibrationPattern=longArrayOf(0,400,200,400)}
                else->ch.setSound(sound,attr)
            }
            manager(c).createNotificationChannel(ch)
        }
    }
    private fun alarmIntent(c:Context)=PendingIntent.getBroadcast(c,7002,Intent(c,WorkAlertReceiver::class.java).setAction("uk.archis.nextdo.ALERT_TICK"),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    private fun nextAlarm(c:Context,whenSeconds:Long?){
        val alarm=c.getSystemService(AlarmManager::class.java)
        alarm.cancel(alarmIntent(c))
        if(whenSeconds!=null){
            val at=maxOf(System.currentTimeMillis()+5000,whenSeconds*1000)
            if(CriticalAlarm.exactAllowed(c))try{alarm.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,at,alarmIntent(c));return}catch(_:SecurityException){}
            alarm.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,at,alarmIntent(c))
        }
    }
    private fun cancelNotices(c:Context){
        CriticalAlarm.stop(c)
        manager(c).activeNotifications.filter{it.tag?.startsWith(tag)==true}.forEach{manager(c).cancel(it.tag,it.id)}
    }
    private fun clear(c:Context){
        vault(c).remove("config");vault(c).remove("state")
        nextAlarm(c,null);cancelNotices(c)
    }
    fun disable(c:Context){
        synchronized(lock){clear(c)}
        WorkManager.getInstance(c).cancelUniqueWork(periodic)
        WorkManager.getInstance(c).cancelUniqueWork(immediate)
        WorkManager.getInstance(c).cancelUniqueWork("nextdo-work-push-refresh")
        WorkPush.clear(c)
    }
    fun enable(c:Context,url:String,token:String,expires:Long){
        WorkPush.clear(c)
        synchronized(lock){
            clear(c)
            write(c,"config",JSONObject().put("url",url).put("token",token).put("expires",expires).put("repeat",15))
        }
        channels(c)
        WorkManager.getInstance(c).enqueueUniquePeriodicWork(periodic,ExistingPeriodicWorkPolicy.KEEP,
            PeriodicWorkRequestBuilder<WorkAlertWorker>(15,TimeUnit.MINUTES).build())
        kick(c)
    }
    fun setRepeat(c:Context,minutes:Int){
        if(minutes !in listOf(1,5,10,15,30,60))return
        CriticalAlarm.save(c,CriticalAlarm.options(c).copy(repeat=minutes))
    }
    fun kick(c:Context){
        if(!enabled(c))return
        WorkManager.getInstance(c).enqueueUniqueWork(immediate,ExistingWorkPolicy.KEEP,OneTimeWorkRequestBuilder<WorkAlertWorker>().build())
    }
    fun alarmActive(c:Context,key:String):Boolean=synchronized(lock){
        if(!CriticalAlarm.valid(key))return@synchronized false
        if(manager(c).activeNotifications.none{it.tag==tag+key&&it.id==id})return@synchronized false
        if(key==CriticalAlarm.TEST)return@synchronized true
        val cfg=read(c,"config")?:return@synchronized false
        val state=read(c,"state")?:return@synchronized false
        if(cfg.optLong("expires")<=now()||now()-state.optLong("synced",0)>=day)return@synchronized false
        val mark=state.optJSONObject("marks")?.optJSONObject(key)?:return@synchronized false
        !mark.optBoolean("ack")
    }
    fun test(c:Context){
        channels(c)
        if(!permission(c))return
        val o=CriticalAlarm.options(c)
        val pi=CriticalAlarm.alarmIntent(c,CriticalAlarm.TEST)
        val b=NotificationCompat.Builder(c,CriticalAlarm.CHANNEL).setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle("NextDo · Prova allarme critico").setContentText("Nessuna scadenza reale. Tocca per gestire.")
            .setCategory(NotificationCompat.CATEGORY_ALARM).setPriority(NotificationCompat.PRIORITY_HIGH)
            .setVisibility(NotificationCompat.VISIBILITY_PRIVATE).setContentIntent(pi)
            .setOngoing(o.persistent).setTimeoutAfter((o.duration+15)*1000L)
            .addAction(0,"Termina prova",CriticalAlarm.action(c,CriticalAlarm.TEST,"uk.archis.nextdo.ALERT_SILENCE"))
        if(o.screen&&CriticalAlarm.fullScreenAllowed(c))b.setFullScreenIntent(pi,true)
        manager(c).notify(tag+CriticalAlarm.TEST,id,b.build())
        CriticalAlarm.launch(c,CriticalAlarm.TEST)
    }
    private fun notice(c:Context,item:JSONObject,loud:Boolean){
        val key=item.getString("key");val priority=item.str("priority")
        val critical=priority=="critical";val o=CriticalAlarm.options(c)
        val channel=when(priority){"critical"->CriticalAlarm.CHANNEL;"high"->"work-high";"low"->"work-low";else->"work-normal"}
        val open=if(critical)CriticalAlarm.alarmIntent(c,key) else PendingIntent.getActivity(c,7004,Intent(c,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val ack=PendingIntent.getBroadcast(c,7005,Intent(c,WorkAlertReceiver::class.java).setAction("uk.archis.nextdo.ALERT_ACK")
            .setData(Uri.parse("nextdo-alert://ack/"+key)),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val kind=if(item.str("kind")=="appointment")"Appuntamento" else "Scadenza"
        val text=if(item.optBoolean("review"))kind+" da verificare. Apri NextDo." else kind+" professionale. Apri NextDo."
        val title=when(priority){"critical"->"NextDo · Allarme critico";"high"->"NextDo · Priorità alta";else->"NextDo · Promemoria"}
        val b=NotificationCompat.Builder(c,channel).setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle(title).setContentText(text)
            .setCategory(if(critical)NotificationCompat.CATEGORY_ALARM else NotificationCompat.CATEGORY_REMINDER)
            .setVisibility(NotificationCompat.VISIBILITY_PRIVATE).setContentIntent(open)
            .setOngoing(if(critical)o.persistent else priority=="high").setAutoCancel(false).setOnlyAlertOnce(false)
            .addAction(NotificationCompat.Action.Builder(0,"Presa visione",ack).setAuthenticationRequired(true).build())
        if(critical){
            b.setPriority(NotificationCompat.PRIORITY_HIGH)
            b.addAction(0,"Silenzia",CriticalAlarm.action(c,key,"uk.archis.nextdo.ALERT_SILENCE"))
            if(loud&&o.screen&&CriticalAlarm.fullScreenAllowed(c))b.setFullScreenIntent(open,true)
        }
        manager(c).notify(tag+key,id,b.build())
    }
    fun acknowledge(c:Context,key:String){
        if(!keyPattern.matches(key))return
        synchronized(lock){
            val state=read(c,"state")?:return
            val marks=state.optJSONObject("marks")?:return
            val entry=marks.optJSONObject(key)?:return
            entry.put("ack",true).put("pending",true);marks.put(key,entry)
            write(c,"state",state);CriticalAlarm.stop(c,key);manager(c).cancel(tag+key,id)
        }
        kick(c)
    }
    fun pendingCount(c:Context):Int=synchronized(lock){try{val marks=read(c,"state")?.optJSONObject("marks")?:return@synchronized 0;marks.keys().asSequence().count{marks.optJSONObject(it)?.optBoolean("pending")==true}}catch(_:Exception){0}}
    private data class Remote(val items:JSONArray,val expires:Long)
    private fun fetch(cfg:JSONObject):Remote{
        val api=TravelApi(cfg.getString("url"));val token=cfg.getString("token")
        val items=JSONArray();var after=0L;var expires=cfg.getLong("expires")
        do{
            val page=api.obj("/work/alerts?after="+after,token)
            expires=minOf(expires,page.getDouble("expires").toLong())
            for(item in page.arr("items")){
                require(keyPattern.matches(item.str("key"))){"Avviso non valido"}
                items.put(item);require(items.length()<=20000){"Troppi avvisi: sincronizzazione incompleta"}
            }
            if(page.isNull("next_after"))break
            val next=page.getLong("next_after");require(next>after);after=next
        }while(true)
        return Remote(items,expires)
    }
    private data class Plan(val stage:Int,val next:Long?)
    private fun plan(item:JSONObject,t:Long):Plan{
        val immediate=item.optBoolean("review")||item.str("priority") in listOf("high","critical")
        val whenSec=if(item.isNull("when"))null else item.optLong("when")
        var stage=if(immediate)1 else 0
        var next:Long?=null
        if(whenSec!=null){
            val rules=mutableListOf(2 to whenSec-day)
            if(item.str("kind")=="appointment"&&!item.optBoolean("date_only")){rules.add(3 to whenSec-3600);rules.add(4 to whenSec-900)}
            rules.add(5 to whenSec)
            for((s,w) in rules){if(w<=t)stage=maxOf(stage,s) else next=next?.let{minOf(it,w)}?:w}
        }
        return Plan(stage,next)
    }
    fun run(c:Context):Boolean=synchronized(runLock){runOnce(c)}
    private fun runOnce(c:Context):Boolean {
        val cfg=synchronized(lock){read(c,"config")}?:return true
        if(cfg.getLong("expires")<=now()){synchronized(lock){if(read(c,"config")?.str("token")==cfg.str("token"))clear(c)};return true}
        var unauthorized=false
        val pending=synchronized(lock){val marks=read(c,"state")?.optJSONObject("marks");marks?.keys()?.asSequence()?.filter{marks.optJSONObject(it)?.optBoolean("pending")==true}?.toList()?:emptyList()}
        val delivered=mutableSetOf<String>()
        for(key in pending.take(100)){
            if(!matches(c,cfg.str("token")))return true
            try{TravelApi(cfg.getString("url")).obj("/work/alerts/ack",cfg.getString("token"),JSONObject().put("key",key));delivered.add(key)}catch(e:Exception){if(e.message?.startsWith("HTTP 404")==true)delivered.add(key)}
        }
        val remote=try{fetch(cfg)}catch(e:Exception){unauthorized=e.message?.startsWith("HTTP 401")==true||e.message?.startsWith("HTTP 403")==true;null}
        synchronized(lock){
            val current=read(c,"config")?:return true
            if(current.str("token")!=cfg.str("token"))return true
            if(unauthorized){clear(c);WorkPush.clear(c);return true}
            val t=now();val state=read(c,"state")?:JSONObject()
            val old=state.optJSONObject("marks")?:JSONObject()
            for(key in delivered)old.optJSONObject(key)?.put("pending",false)
            val items=remote?.items?:state.optJSONArray("items")?:JSONArray()
            val last=if(remote!=null)t else state.optLong("synced",0)
            if(remote!=null){current.put("expires",remote.expires);write(c,"config",current)}
            if(t-last>=day||current.getLong("expires")<=t){cancelNotices(c);nextAlarm(c,null);return remote!=null}
            val marks=JSONObject();val keys=mutableSetOf<String>()
            var next:Long?=null
            fun upcoming(w:Long?){if(w!=null&&w>t)next=next?.let{minOf(it,w)}?:w}
            val sorted=(0 until items.length()).mapNotNull{items.optJSONObject(it)}
                .sortedBy{when(it.str("priority")){"critical"->0;"high"->1;"normal"->2;else->3}}
            var sent=0
            var loudKey:String?=null
            for(item in sorted){
                val key=item.str("key");if(!keyPattern.matches(key))continue
                keys.add(key)
                val mark=old.optJSONObject(key)?:JSONObject();marks.put(key,mark)
                if(item.optBoolean("acknowledged")){mark.put("ack",true).put("pending",false);CriticalAlarm.stop(c,key);manager(c).cancel(tag+key,id);continue}
                if(mark.optBoolean("ack"))continue
                val p=plan(item,t);upcoming(p.next)
                val critical=item.str("priority")=="critical"
                val repeat=CriticalAlarm.options(c).repeat*60L
                val lastSent=mark.optLong("sent",0)
                val needs=p.stage>0&&(p.stage>mark.optInt("stage",0)||(critical&&t-lastSent>=repeat))
                if(needs&&sent<10&&permission(c)){
                    val loud=critical&&loudKey==null
                    notice(c,item,loud);if(loud)loudKey=key
                    mark.put("stage",p.stage).put("sent",t);sent++
                }else if(needs&&permission(c))upcoming(t+60)
                if(critical&&p.stage>0&&permission(c))upcoming(maxOf(t+60,mark.optLong("sent",t)+repeat))
            }
            manager(c).activeNotifications.filter{it.tag?.startsWith(tag)==true&&it.tag!=tag+"test"&&it.tag?.removePrefix(tag) !in keys}.forEach{CriticalAlarm.stop(c,it.tag?.removePrefix(tag));manager(c).cancel(it.tag,it.id)}
            for(key in old.keys().asSequence())if(old.optJSONObject(key)?.optBoolean("pending")==true&&!marks.has(key))marks.put(key,old.getJSONObject(key))
            write(c,"state",JSONObject().put("items",items).put("marks",marks).put("synced",last))
            upcoming(last+day);upcoming(current.getLong("expires"))
            nextAlarm(c,next)
            loudKey?.let{CriticalAlarm.launch(c,it)}
        }
        if(remote!=null)try{WorkPush.sync(c,cfg)}catch(_:Exception){}
        if(pendingCount(c)>0)return false
        return remote!=null
    }
    fun kickPush(c:Context){
        if(!enabled(c))return
        val request=OneTimeWorkRequestBuilder<WorkAlertWorker>()
        if(Build.VERSION.SDK_INT>=31)request.setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
        WorkManager.getInstance(c).enqueueUniqueWork("nextdo-work-push-refresh",ExistingWorkPolicy.APPEND_OR_REPLACE,request.build())
    }
}

class WorkAlertWorker(context:Context,params:WorkerParameters):Worker(context,params){
    override fun doWork():Result=try{if(WorkAlerts.run(applicationContext))Result.success() else Result.retry()}catch(_:Exception){Result.retry()}
}
class WorkAlertReceiver:BroadcastReceiver(){
    override fun onReceive(context:Context,intent:Intent){
        when(intent.action){
            "uk.archis.nextdo.ALERT_TICK"->WorkAlerts.kick(context)
            "uk.archis.nextdo.ALERT_SILENCE"->{
                val key=intent.data?.lastPathSegment?:return
                if(key==CriticalAlarm.TEST)CriticalAlarm.finishTest(context)
                else if(CriticalAlarm.valid(key))CriticalAlarm.stop(context,key)
            }
            "uk.archis.nextdo.ALERT_ACK"->{
                val key=intent.data?.lastPathSegment?:return
                val pending=goAsync()
                Thread{try{WorkAlerts.acknowledge(context,key)}finally{pending.finish()}}.start()
            }
        }
    }
}
