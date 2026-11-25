package uk.archis.nextdoviaggi

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.work.*
import org.json.JSONObject
import org.json.JSONArray
import java.util.concurrent.TimeUnit

internal object PrivateAlerts {
    private val lock=Any()
    private const val periodic="nextdo-private-alert-periodic"
    private const val nowWork="nextdo-private-alert-now"
    private const val channel="nextdo-private-reminders"
    private const val tag="nextdo-private-reminder"
    private fun vault(c:Context)=Vault(c,true)
    private fun read(c:Context,name:String):JSONObject?{
        val v=vault(c)
        return if(v.exists(name))JSONObject(String(v.read(name),Charsets.UTF_8)) else null
    }
    private fun write(c:Context,name:String,value:JSONObject)=vault(c).write(name,value.toString().toByteArray(Charsets.UTF_8))
    fun enabled(c:Context)=synchronized(lock){vault(c).exists("private_config")}
    fun enable(c:Context,url:String,token:String,expires:Long){
        disable(c)
        synchronized(lock){write(c,"private_config",JSONObject().put("url",url).put("token",token).put("expires",expires))}
        c.getSystemService(NotificationManager::class.java).createNotificationChannel(NotificationChannel(channel,"Personale · Promemoria",NotificationManager.IMPORTANCE_DEFAULT).apply{lockscreenVisibility=android.app.Notification.VISIBILITY_PRIVATE})
        WorkManager.getInstance(c).enqueueUniquePeriodicWork(periodic,ExistingPeriodicWorkPolicy.KEEP,PeriodicWorkRequestBuilder<PrivateAlertWorker>(15,TimeUnit.MINUTES).setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()).build())
        kick(c)
    }
    fun disable(c:Context){
        synchronized(lock){vault(c).remove("private_config");vault(c).remove("private_marks");c.getSystemService(NotificationManager::class.java).cancel(tag,7101)}
        WorkManager.getInstance(c).cancelUniqueWork(periodic);WorkManager.getInstance(c).cancelUniqueWork(nowWork)
    }
    fun kick(c:Context){
        if(enabled(c))WorkManager.getInstance(c).enqueueUniqueWork(nowWork,ExistingWorkPolicy.KEEP,OneTimeWorkRequestBuilder<PrivateAlertWorker>().setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()).build())
    }
    fun run(c:Context):Boolean{
        val cfg=synchronized(lock){read(c,"private_config")}?:return true
        if(cfg.optLong("expires")<=System.currentTimeMillis()/1000){synchronized(lock){if(read(c,"private_config")?.str("token")==cfg.str("token"))disable(c)};return true}
        val response=try{TravelApi(cfg.str("url")).obj("/private-alerts",cfg.str("token"))}catch(e:TravelHttpException){
            if(e.status==401||e.status==403){synchronized(lock){if(read(c,"private_config")?.str("token")==cfg.str("token"))disable(c)};return true}
            return false
        }catch(_:Exception){return false}
        synchronized(lock){
            if(read(c,"private_config")?.str("token")!=cfg.str("token"))return true
            if(!WorkAlerts.permission(c))return true
            val stored=read(c,"private_marks")?.optJSONArray("keys")?:JSONArray()
            val old=(0 until stored.length()).map{stored.optString(it)}.toSet()
            val keys=response.arr("items").map{it.str("key")}.filter{it.matches(Regex("[a-f0-9]{64}"))}.distinct()
            if(keys.any{it !in old}){
                val open=PendingIntent.getActivity(c,7101,Intent(c,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
                val notice=NotificationCompat.Builder(c,channel).setSmallIcon(android.R.drawable.ic_dialog_info)
                    .setContentTitle("NextDo · Promemoria personale").setContentText("Hai impegni personali da consultare.")
                    .setVisibility(NotificationCompat.VISIBILITY_PRIVATE).setCategory(NotificationCompat.CATEGORY_REMINDER)
                    .setContentIntent(open).setAutoCancel(true).build()
                c.getSystemService(NotificationManager::class.java).notify(tag,7101,notice)
            }
            write(c,"private_marks",JSONObject().put("keys",JSONArray(keys)))
        }
        return true
    }
}
class PrivateAlertWorker(context:Context,params:WorkerParameters):Worker(context,params){
    override fun doWork():Result=try{if(PrivateAlerts.run(applicationContext))Result.success() else Result.retry()}catch(_:Exception){Result.retry()}
}
