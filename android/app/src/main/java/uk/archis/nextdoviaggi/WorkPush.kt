package uk.archis.nextdoviaggi

import android.app.Application
import android.content.Context
import com.google.firebase.FirebaseApp
import com.google.firebase.FirebaseOptions
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.google.android.gms.tasks.Tasks
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class NextDoApplication:Application(){
    override fun onCreate(){
        super.onCreate()
        WorkPush.initializeSaved(this)
    }
}
internal object WorkPush{
    private val lock=Any()
    private fun vault(c:Context)=Vault(c,true)
    fun initializeSaved(c:Context){
        try{
            val v=vault(c)
            if(WorkAlerts.enabled(c)&&v.exists("firebase"))initialize(c,JSONObject(String(v.read("firebase"),Charsets.UTF_8)))
        }catch(_:Exception){}
    }
    private fun initialize(c:Context,p:JSONObject):FirebaseApp?=synchronized(lock){
        val existing=FirebaseApp.getApps(c).firstOrNull{it.name==FirebaseApp.DEFAULT_APP_NAME}
        if(existing!=null){
            return@synchronized if(existing.options.applicationId==p.getString("app_id")&&existing.options.projectId==p.getString("project_id")&&existing.options.apiKey==p.getString("api_key"))existing else null
        }
        FirebaseApp.initializeApp(c,FirebaseOptions.Builder()
            .setApplicationId(p.getString("app_id")).setApiKey(p.getString("api_key"))
            .setProjectId(p.getString("project_id")).setGcmSenderId(p.getString("sender_id")).build())
    }
    fun sync(c:Context,cfg:JSONObject){
        val secret=cfg.getString("token")
        val api=TravelApi(cfg.getString("url"))
        val p=api.obj("/work/alerts/push/config",secret).optJSONObject("config")
        if(!WorkAlerts.matches(c,secret))return
        if(p==null){clear(c);return}
        val v=vault(c)
        v.write("firebase",p.toString().toByteArray(Charsets.UTF_8))
        val app=initialize(c,p)?:return // Restart app after changing Firebase project.
        val messaging=FirebaseMessaging.getInstance()
        val registration=Tasks.await(messaging.token,15,TimeUnit.SECONDS)
        if(!WorkAlerts.matches(c,secret))return
        api.obj("/work/alerts/push/register",secret,JSONObject().put("token",registration).put("project_id",p.getString("project_id")))
        if(WorkAlerts.matches(c,secret))v.write("push_status",JSONObject().put("registered",System.currentTimeMillis()).toString().toByteArray())
    }
    fun active(c:Context):Boolean=try{
        val v=vault(c)
        WorkAlerts.enabled(c)&&v.exists("push_status")&&System.currentTimeMillis()-JSONObject(String(v.read("push_status"),Charsets.UTF_8)).optLong("registered")<86400000L
    }catch(_:Exception){false}
    fun clear(c:Context){
        try{vault(c).remove("firebase");vault(c).remove("push_status")
            if(FirebaseApp.getApps(c).any{it.name==FirebaseApp.DEFAULT_APP_NAME})FirebaseMessaging.getInstance().deleteToken()
        }catch(_:Exception){}
    }
}
class NextDoMessagingService:FirebaseMessagingService(){
    override fun onMessageReceived(message:RemoteMessage){
        if(message.data["nextdo"]=="work_refresh")WorkAlerts.kickPush(applicationContext)
    }
    override fun onNewToken(token:String){WorkAlerts.kick(applicationContext)}
    override fun onDeletedMessages(){WorkAlerts.kickPush(applicationContext)}
}
