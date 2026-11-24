package uk.archis.nextdoviaggi

import android.Manifest
import android.app.*
import android.content.*
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.location.*
import android.os.*
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import org.json.JSONObject
import org.json.JSONArray
import java.security.KeyStore
import java.security.MessageDigest
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

// The diary key is separate from the interactive vault: recording must survive screen lock.
class DiaryStore(private val ctx:Context):SQLiteOpenHelper(ctx,"diary.db",null,1) {
    override fun onCreate(db:SQLiteDatabase) {
        db.execSQL("CREATE TABLE points(scope TEXT NOT NULL, trip TEXT NOT NULL, id TEXT PRIMARY KEY, payload BLOB NOT NULL)")
        db.execSQL("CREATE INDEX diary_pending ON points(scope,trip)")
    }
    override fun onUpgrade(db:SQLiteDatabase,oldVersion:Int,newVersion:Int) = Unit
    private fun key():SecretKey = synchronized(DiaryStore::class.java) {
        val ks=KeyStore.getInstance("AndroidKeyStore").apply{load(null)}
        (ks.getKey("nextdo_diary_v1",null) as? SecretKey) ?: KeyGenerator.getInstance("AES","AndroidKeyStore").run {
            init(KeyGenParameterSpec.Builder("nextdo_diary_v1",KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
            generateKey()
        }
    }
    private fun aad(scope:String,trip:String,id:String)=JSONObject().put("scope",scope).put("trip",trip).put("id",id).toString().toByteArray()
    fun append(scope:String,trip:String,point:JSONObject) {
        val id=point.getString("id")
        val cipher=Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE,key());cipher.updateAAD(aad(scope,trip,id))
        val data=cipher.iv+cipher.doFinal(point.toString().toByteArray())
        writableDatabase.insertOrThrow("points",null,ContentValues().apply{put("scope",scope);put("trip",trip);put("id",id);put("payload",data)})
    }
    fun count(scope:String,trip:String):Int=readableDatabase.rawQuery("SELECT COUNT(*) FROM points WHERE scope=? AND trip=?",arrayOf(scope,trip)).use{it.moveToFirst();it.getInt(0)}
    fun batch(scope:String,trip:String):List<JSONObject> {
        val out=mutableListOf<JSONObject>()
        readableDatabase.rawQuery("SELECT id,payload FROM points WHERE scope=? AND trip=? ORDER BY rowid LIMIT 200",arrayOf(scope,trip)).use { c ->
            while(c.moveToNext()){
                val id=c.getString(0);val raw=c.getBlob(1)
                val cipher=Cipher.getInstance("AES/GCM/NoPadding")
                cipher.init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,raw.copyOfRange(0,12)))
                cipher.updateAAD(aad(scope,trip,id))
                out.add(JSONObject(String(cipher.doFinal(raw.copyOfRange(12,raw.size)),Charsets.UTF_8)))
            }
        }
        return out
    }
    fun ack(scope:String,trip:String,points:List<JSONObject>) {
        val db=writableDatabase;db.beginTransaction()
        try { points.forEach{db.delete("points","scope=? AND trip=? AND id=?",arrayOf(scope,trip,it.getString("id")))};db.setTransactionSuccessful() }
        finally{db.endTransaction()}
    }
    fun discardAll(){writableDatabase.delete("points",null,null)}
    companion object {
        fun scope(cfg:JSONObject):String=MessageDigest.getInstance("SHA-256").digest((cfg.getString("url")+"\n"+cfg.getString("token")).toByteArray()).joinToString(""){"%02x".format(it.toInt() and 255)}
    }
}

object DiaryState {
    private fun prefs(c:Context)=c.getSharedPreferences("diary_control",Context.MODE_PRIVATE)
    fun trip(c:Context)=prefs(c).getString("trip","").orEmpty()
    fun scope(c:Context)=prefs(c).getString("scope","").orEmpty()
    fun wanted(c:Context)=prefs(c).getBoolean("wanted",false)
    @Volatile var running=false
    fun start(c:Context,scope:String,trip:String){
        check(!wanted(c) || (DiaryState.trip(c)==trip && DiaryState.scope(c)==scope)){"Sospendi prima il diario già attivo"}
        check(prefs(c).edit().putString("scope",scope).putString("trip",trip).putBoolean("wanted",true).commit())
        try{c.startForegroundService(Intent(c,DiaryService::class.java))}
        catch(e:Exception){stop(c);throw e}
    }
    fun stop(c:Context){
        prefs(c).edit().putBoolean("wanted",false).commit()
        c.stopService(Intent(c,DiaryService::class.java))
    }
    fun precise(c:Context)=c.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED
    fun background(c:Context)=c.checkSelfPermission(Manifest.permission.ACCESS_BACKGROUND_LOCATION)==PackageManager.PERMISSION_GRANTED
    fun notifications(c:Context)= (Build.VERSION.SDK_INT<33 || c.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)==PackageManager.PERMISSION_GRANTED) && c.getSystemService(NotificationManager::class.java).areNotificationsEnabled()
}

class DiaryService:Service(),LocationListener {
    private lateinit var lm:LocationManager
    private lateinit var store:DiaryStore
    private var trip=""
    private var scope=""
    private var segment=""
    private var last:Location?=null
    override fun onCreate(){super.onCreate();lm=getSystemService(LocationManager::class.java);store=DiaryStore(this)}
    override fun onBind(intent:Intent?)=null
    override fun onStartCommand(intent:Intent?,flags:Int,startId:Int):Int {
        if(intent?.action=="STOP"){DiaryState.stop(this);return START_NOT_STICKY}
        if(DiaryState.running)return START_STICKY
        if(!DiaryState.wanted(this)||!DiaryState.precise(this)||!DiaryState.notifications(this)){stopSelf();return START_NOT_STICKY}
        trip=DiaryState.trip(this);scope=DiaryState.scope(this)
        if(trip.isBlank()||scope.isBlank()){stopSelf();return START_NOT_STICKY}
        val nm=getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel("diary","Diario di bordo",NotificationManager.IMPORTANCE_LOW))
        val open=PendingIntent.getActivity(this,1,Intent(this,MainActivity::class.java),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val stop=PendingIntent.getService(this,2,Intent(this,DiaryService::class.java).setAction("STOP"),PendingIntent.FLAG_IMMUTABLE)
        try {
            val n=Notification.Builder(this,"diary").setSmallIcon(android.R.drawable.ic_menu_mylocation)
                .setContentTitle("NextDo · Diario di bordo").setContentText("Registrazione GPS attiva").setOngoing(true)
                .setVisibility(Notification.VISIBILITY_PRIVATE).setContentIntent(open)
                .addAction(Notification.Action.Builder(android.graphics.drawable.Icon.createWithResource(this,android.R.drawable.ic_media_pause),"Sospendi",stop).build()).build()
            startForeground(412,n,ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION)
            segment=UUID.randomUUID().toString();last=null
            lm.requestLocationUpdates(LocationManager.GPS_PROVIDER,30_000L,20f,this,Looper.getMainLooper())
            DiaryState.running=true
            return START_STICKY
        } catch(e:Exception){stopSelf();return START_NOT_STICKY}
    }
    override fun onLocationChanged(location:Location) {
        if(!DiaryState.wanted(this)||!DiaryState.running)return
        if(!location.hasAccuracy()||location.accuracy>100f||location.time<=0||System.currentTimeMillis()-location.time>120_000)return
        val previous=last
        if(previous!=null&&location.time<=previous.time)return
        if(previous!=null&&location.time-previous.time>300_000)segment=UUID.randomUUID().toString()
        try{
            store.append(scope,trip,JSONObject().put("id",UUID.randomUUID().toString()).put("segment",segment)
                .put("timestamp",location.time).put("latitude",location.latitude).put("longitude",location.longitude).put("accuracy",location.accuracy.toDouble()))
            last=location
        }catch(e:Exception){stopSelf()}
    }
    override fun onProviderDisabled(provider:String){stopSelf()}
    override fun onProviderEnabled(provider:String){}
    override fun onStatusChanged(provider:String?,status:Int,extras:Bundle?){}
    override fun onDestroy(){DiaryState.running=false;lm.removeUpdates(this);store.close();super.onDestroy()}
}
class DiaryBoot:BroadcastReceiver(){
    override fun onReceive(context:Context,intent:Intent){
        if(intent.action==Intent.ACTION_BOOT_COMPLETED && DiaryState.wanted(context) && DiaryState.precise(context) && DiaryState.background(context) && DiaryState.notifications(context)){
            try{context.startForegroundService(Intent(context,DiaryService::class.java))}catch(_:Exception){}
        }
    }
}
