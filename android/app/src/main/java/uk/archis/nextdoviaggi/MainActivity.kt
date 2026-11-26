package uk.archis.nextdoviaggi

import android.hardware.biometrics.BiometricManager
import android.hardware.biometrics.BiometricPrompt
import android.os.CancellationSignal
import android.os.Handler
import android.os.Looper
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.pdf.PdfRenderer
import android.net.Uri
import android.provider.Settings
import androidx.core.content.FileProvider
import android.os.Bundle
import android.os.ParcelFileDescriptor
import android.util.Base64
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.CancellationException
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.time.LocalDate
import java.time.temporal.ChronoUnit

private val Navy = Color(0xFF0B1726)
private val Panel = Color(0xFF172B3D)
private val Teal = Color(0xFF69E0D2)
private val Sand = Color(0xFFFFD49A)
private val Muted = Color(0xFFADC1D2)
private val White = Color(0xFFF3F8FC)

class MainActivity : ComponentActivity() {
    private lateinit var vault: Vault
    private var locked by mutableStateOf(true)
    private var area by mutableStateOf(NextDoArea.HOME)
    private var personalAppearance by mutableStateOf<JSONObject?>(null)
    private var appearanceError by mutableStateOf("")
    private var privateAgenda by mutableStateOf<List<JSONObject>?>(null)
    private var privateSection by mutableStateOf("")
    private var privateProblem by mutableStateOf("")
    private var privateAlertsEnabled by mutableStateOf(false)
    private fun togglePrivateAlerts(){
        val cfg=connection
        val s=session
        if(privateAlertsEnabled){
            PrivateAlerts.disable(this);privateAlertsEnabled=false
            if(cfg!=null&&s.isNotBlank())task({TravelApi(cfg.str("url")).obj("/private-alerts/disable",s,JSONObject())}){}
        }else{
            if(!WorkAlerts.permission(this)){if(android.os.Build.VERSION.SDK_INT>=33)notificationPermission.launch(android.Manifest.permission.POST_NOTIFICATIONS);return}
            if(cfg==null||s.isBlank())return
            task({
                val r=TravelApi(cfg.str("url")).obj("/private-alerts/enable",s,JSONObject())
                PrivateAlerts.enable(this,cfg.str("url"),r.str("token"),r.optDouble("expires").toLong())
            }){privateAlertsEnabled=PrivateAlerts.enabled(this)}
        }
    }
    private fun refreshPrivateAgenda(){
        val cfg=connection?:return
        val s=session
        if(locked||s.isBlank())return
        task({TravelApi(cfg.getString("url")).obj("/items",s).arr("items")}){privateAgenda=it;privateProblem=""}
    }
    private fun savePrivateItem(id:String,body:JSONObject){
        val cfg=connection?:return
        val s=session
        if(locked||s.isBlank())return
        task({
            val api=TravelApi(cfg.getString("url"))
            api.obj("/items"+if(id.isBlank())"" else "/"+segment(id),s,body)
            api.obj("/items",s).arr("items")
        }){privateAgenda=it;privateProblem=""}
    }
    private fun deletePrivateItem(id:String){
        val cfg=connection?:return
        val s=session
        if(locked||s.isBlank()||id.isBlank())return
        task({
            val api=TravelApi(cfg.getString("url"))
            api.obj("/items/"+segment(id)+"/delete",s,JSONObject())
            api.obj("/items",s).arr("items")
        }){privateAgenda=it;privateProblem=""}
    }
    private var appearancePhoto by mutableStateOf<Uri?>(null)
    private var appearancePhotoOwner=""
    private val appearancePicker=registerForActivityResult(ActivityResultContracts.GetContent()){uri->
        appearancePhoto=uri
    }
    private fun chooseAppearancePhoto(){
        val cfg=connection?:return
        if(locked||session.isBlank()||busy)return
        appearancePhotoOwner=timelineOwner(cfg);appearancePhoto=null
        appearancePicker.launch("image/*")
    }
    private fun savePersonalAppearance(body:JSONObject){
        val cfg=connection?:return
        val s=session
        if(locked||s.isBlank())return
        task({TravelApi(cfg.getString("url")).obj("/appearance",s,body)}){personalAppearance=it;appearanceError=""}
    }
    private fun uploadAppearancePhoto(){
        val cfg=connection?:return
        val uri=appearancePhoto?:return
        val s=session
        if(locked||s.isBlank()||appearancePhotoOwner!=timelineOwner(cfg))return
        task({
            val raw=contentResolver.openInputStream(uri)?.use { input ->
                val out=java.io.ByteArrayOutputStream()
                val buffer=ByteArray(8192)
                var count=input.read(buffer)
                while(count!=-1){require(out.size()+count<=5*1024*1024){"Foto oltre 5 MB"};out.write(buffer,0,count);count=input.read(buffer)}
                out.toByteArray()
            }?:error("Fotografia non disponibile")
            TravelApi(cfg.getString("url")).obj("/appearance/photo",s,JSONObject().put("image",Base64.encodeToString(raw,Base64.NO_WRAP)))
        }){personalAppearance=it;appearancePhoto=null;appearancePhotoOwner="";appearanceError=""}
    }
    private var workFilter by mutableStateOf("all")
    private var allowWorkScreenshots by mutableStateOf(true)
    private var allowPersonalScreenshots by mutableStateOf(true)
    private var allowTravelScreenshots by mutableStateOf(false)
    private var foreground by mutableStateOf(false)
    private fun updateCaptureProtection(){
        val allowed=foreground&&!locked&&android.os.Build.VERSION.SDK_INT>=33&&when(area){
            NextDoArea.HOME,NextDoArea.WORK -> allowWorkScreenshots
            NextDoArea.PERSONAL -> allowPersonalScreenshots
            NextDoArea.TRIPS -> allowTravelScreenshots
            NextDoArea.SETTINGS -> false
        }
        if(allowed)window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE) else window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
    }
    private var workConnection by mutableStateOf<JSONObject?>(null)
    private var workAgenda by mutableStateOf<WorkAgenda?>(null)
    private var workDetail by mutableStateOf<JSONObject?>(null)
    private var workError by mutableStateOf("")
    private var workBusy by mutableStateOf(false)
    private var alertsEnabled by mutableStateOf(false)
    private var alarmOptions by mutableStateOf(AlarmOptions())
    private var fullScreenAllowed by mutableStateOf(false)
    private var exactAlarmAllowed by mutableStateOf(false)
    private val ringtonePicker=registerForActivityResult(ActivityResultContracts.StartActivityForResult()){result->
        if(result.resultCode==RESULT_OK){
            @Suppress("DEPRECATION")
            val uri=result.data?.getParcelableExtra<Uri>(android.media.RingtoneManager.EXTRA_RINGTONE_PICKED_URI)
            if(uri!=null&&uri.scheme=="content")saveAlarmOptions(alarmOptions.copy(sound="custom",custom=uri.toString()))
        }
    }
    private var alertPermission by mutableStateOf(false)
    private val notificationPermission=registerForActivityResult(ActivityResultContracts.RequestPermission()){ alertPermission=WorkAlerts.permission(this) }
    private var availableUpdate by mutableStateOf<TravelUpdate?>(null)
    private var updateBusy by mutableStateOf(false)
    private var updateMessage by mutableStateOf("")
    private var showUpdateNotes by mutableStateOf(false)
    private fun checkUpdates(manual: Boolean = false) {
        if (updateBusy) return
        updateBusy = true; updateMessage = ""
        lifecycleScope.launch {
            try {
                availableUpdate = withContext(Dispatchers.IO) { AppUpdates.check(this@MainActivity) }
                if (manual && availableUpdate == null) updateMessage = "Nessun aggiornamento disponibile"
            } catch (e: CancellationException) { throw e }
            catch (_: Exception) {
                if (manual) updateMessage = "Impossibile verificare gli aggiornamenti. Riprova con una connessione Internet."
            } finally { updateBusy = false }
        }
    }
    private fun installUpdate() {
        val update = availableUpdate ?: return
        if (updateBusy) return
        if (!packageManager.canRequestPackageInstalls()) {
            updateMessage = "Autorizza NextDo a installare app da questa fonte, poi torna qui e riprova."
            try {
                startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + packageName)))
            } catch (_: Exception) {
                updateMessage = "Apri Impostazioni Android e autorizza l’installazione da NextDo."
            }
            return
        }
        updateBusy = true; updateMessage = ""
        lifecycleScope.launch {
            try {
                val apk = withContext(Dispatchers.IO) { AppUpdates.download(this@MainActivity, update) }
                val uri = FileProvider.getUriForFile(this@MainActivity, packageName + ".updates", apk)
                startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive")
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION))
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { updateMessage = e.message?.take(200) ?: "Aggiornamento non riuscito" }
            finally { updateBusy = false }
        }
    }
    private var authenticating by mutableStateOf(false)
    private var busy by mutableStateOf(false)
    private var error by mutableStateOf("")
    private var connection by mutableStateOf<JSONObject?>(null)
    private var session by mutableStateOf("")
    private var travelAuthState by mutableStateOf(TravelAuthState.PIN_REQUIRED)
    private var trips by mutableStateOf<List<JSONObject>>(emptyList())
    private var current by mutableStateOf<TripPackage?>(null)
    private var pendingZip by mutableStateOf<Uri?>(null)
    private var zipScope = ""
    private var editor by mutableStateOf<TravelEditor?>(null)
    private val zipPicker = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if(uri != null) pendingZip = uri
    }
    private var offline by mutableStateOf(false)
    private var offlineMeta by mutableStateOf<JSONObject?>(null)
    private var offlineSyncBusy by mutableStateOf(false)
    private var offlineSyncStatus by mutableStateOf("")
    private var offlineOpenedStamp by mutableStateOf("")
    private var offlineLastChecked by mutableStateOf("")
    private val offlineGuard=Any()
    private var offlineSyncGeneration=0
    private fun readOfflineMeta(cfg:JSONObject?):JSONObject? {
        if(cfg==null)return null
        return synchronized(offlineGuard){
            if(vault.exists(OFFLINE_FILE)) OfflineSnapshot.decode(vault.read(OFFLINE_FILE),timelineOwner(cfg)).meta
            else if(vault.exists("offline_meta")&&vault.exists("offline")) JSONObject(String(vault.read("offline_meta"),Charsets.UTF_8))
            else null
        }
    }
    private fun clearOfflineFiles(){
        synchronized(offlineGuard){
            vault.remove(OFFLINE_FILE);vault.remove("offline");vault.remove("offline_meta")
        }
    }
    private var section by mutableStateOf("Home")
    // Only retain the picker URI, not the raw history, across the normal app lock.
    private var timelineFile by mutableStateOf<Uri?>(null)
    private var timelineTrip = ""
    private var timelineScope = ""
    private val timelinePicker=registerForActivityResult(ActivityResultContracts.GetContent()){uri->
        timelineFile=uri
    }
    private fun timelineOwner(cfg:JSONObject)=java.security.MessageDigest.getInstance("SHA-256")
        .digest((cfg.str("url")+"\n"+cfg.str("token")).toByteArray()).joinToString(""){"%02x".format(it.toInt() and 255)}

    private var selectedDay by mutableStateOf("")
    private var pdf by mutableStateOf<ByteArray?>(null)
    private var pdfName by mutableStateOf("")
    private var pdfMessage by mutableStateOf("")
    private var pageCount by mutableStateOf(0)
    private var pageBitmap by mutableStateOf<Bitmap?>(null)
    @Volatile private var epoch = 0
    private var authCancel: CancellationSignal? = null
    private val authHandler = Handler(Looper.getMainLooper())
    private val autoLock = Runnable { lockLocal() }
    private val authenticators = BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.DEVICE_CREDENTIAL
    private data class ResumeResult(val token:String="",val trips:List<JSONObject> = emptyList(),val error:String="",val authState:TravelAuthState=TravelAuthState.PIN_REQUIRED)
    private fun resumeServer(cfg:JSONObject):ResumeResult {
        val remembered=cfg.optString("remember_token")
        if(remembered.isBlank()) return ResumeResult()
        return try {
            val api=TravelApi(cfg.getString("url"))
            val response=try {
                api.obj("/resume",cfg.getString("token"),JSONObject().put("remember_token",remembered))
            } catch(e:TravelHttpException) {
                val state=resumeFailure(e.status,e.detail)
                return ResumeResult(error=when(state){
                    TravelAuthState.PIN_REQUIRED -> "L’autorizzazione del telefono deve essere confermata di nuovo."
                    TravelAuthState.REPAIR_REQUIRED -> "Dispositivo scaduto o non più autorizzato. Associalo nuovamente dal Web."
                    else -> "Connessione automatica non riuscita. Riprova senza reinserire il PIN."
                },authState=state)
            }
            val s=response.getString("session_token")
            ResumeResult(s,api.trips(s),authState=TravelAuthState.CONNECTED)
        } catch(e:Exception) {
            ResumeResult(error="Connessione automatica non riuscita. Verifica la rete e riprova.",authState=TravelAuthState.RETRY)
        }
    }
    private fun retryServer() {
        val cfg=connection ?: return
        task({resumeServer(cfg)}) { r -> session=r.token;trips=r.trips;error=r.error;travelAuthState=r.authState }
    }
    private data class DeviceUnlockData(val cfg:JSONObject?,val meta:JSONObject?,val resumed:ResumeResult,val work:JSONObject?,val offlineProblem:String="")
    private fun finishDeviceUnlock() {
        task({
            val cfg = if (vault.exists("connection")) JSONObject(String(vault.read("connection"), Charsets.UTF_8)) else null
            val metaResult=runCatching{readOfflineMeta(cfg)}
            val meta=metaResult.getOrNull()
            val work=if(vault.exists("work_connection")) JSONObject(String(vault.read("work_connection"),Charsets.UTF_8)) else null
            DeviceUnlockData(cfg,meta,if(cfg!=null)resumeServer(cfg) else ResumeResult(),work,if(metaResult.isFailure)"Copia offline non leggibile. Nessun file è stato cancellato; scarica una nuova copia." else "")
        }) { (cfg, meta, resumed, work, offlineProblem) ->
            workConnection=work
            offlineSyncStatus=offlineProblem
            connection = cfg; offlineMeta = meta; locked = false; session=resumed.token; trips=resumed.trips; error=resumed.error;travelAuthState=resumed.authState
            updateCaptureProtection()
            authHandler.removeCallbacks(autoLock)
            authHandler.postDelayed(autoLock, 300_000L)
        }
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT)
        )
        window.isNavigationBarContrastEnforced = false
        window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        if(android.os.Build.VERSION.SDK_INT>=33)setRecentsScreenshotEnabled(false)
        allowWorkScreenshots=getPreferences(MODE_PRIVATE).getBoolean("allow_work_screenshots",true)
        allowPersonalScreenshots=getPreferences(MODE_PRIVATE).getBoolean("allow_personal_screenshots",true)
        allowTravelScreenshots=getPreferences(MODE_PRIVATE).getBoolean("allow_travel_screenshots",false)
        vault = Vault(this)
        checkUpdates()
        WorkAlerts.channels(this)
        refreshAlertStatus()
        // Any leftovers from an interrupted PDF render are local and deleted on startup.
        cacheDir.listFiles()?.filter { it.name.startsWith("travel-pdf-") }?.forEach { it.delete() }
        PdfExport.cleanup(this)
        setContent {
            MaterialTheme(colorScheme = darkColorScheme(primary = Teal, onPrimary = Navy, background = Navy, surface = Panel,
                onSurface = White, onBackground = White, secondary = Sand, onSurfaceVariant = Muted)) {
                Surface(Modifier.fillMaxSize(), color = Navy) { App() }
            }
        }
    }
    override fun onResume() {
        super.onResume()
        foreground=true;updateCaptureProtection()
        refreshAlertStatus()
        if(alertsEnabled)WorkAlerts.kick(this)
        privateAlertsEnabled=PrivateAlerts.enabled(this)
        if(privateAlertsEnabled)PrivateAlerts.kick(this)
    }
    private fun refreshAlertStatus(){
        alertPermission=WorkAlerts.permission(this)
        alertsEnabled=WorkAlerts.enabled(this)
        alarmOptions=CriticalAlarm.options(this)
        fullScreenAllowed=CriticalAlarm.fullScreenAllowed(this)
        exactAlarmAllowed=CriticalAlarm.exactAllowed(this)
    }
    private fun saveAlarmOptions(o:AlarmOptions){CriticalAlarm.save(this,o);alarmOptions=o}
    private fun alarmSettings(action:String){try{startActivity(Intent(action,Uri.parse("package:"+packageName)))}catch(_:Exception){workError="Impostazione non disponibile su questo dispositivo."}}
    override fun onPause(){
        foreground=false;updateCaptureProtection()
        super.onPause()
    }
    override fun onStop() {
        super.onStop()
        if (!authenticating) lockLocal()
    }
    private fun lockLocal() {
        synchronized(offlineGuard){epoch++}
        offlineSyncGeneration++;offlineSyncBusy=false;offlineSyncStatus="";offlineOpenedStamp="";offlineLastChecked=""
        authHandler.removeCallbacks(autoLock)
        val pending = authCancel
        authCancel = null
        authenticating = false
        pending?.cancel()
        locked = true; busy = false; connection = null; session = ""; trips = emptyList();travelAuthState=TravelAuthState.PIN_REQUIRED
        personalAppearance=null;appearanceError="";privateAgenda=null;privateSection="";privateProblem=""
        workConnection=null;workAgenda=null;workDetail=null;workError="";workBusy=false
        editor = null; current = null; offlineMeta = null; offline = false; closePdf(); error = ""
        section = "Home"; area=NextDoArea.HOME;workFilter="all";updateCaptureProtection()
    }
    private fun deviceUnlock() {
        if (authenticating || busy) return
        val bm = getSystemService(BiometricManager::class.java)
        when (bm.canAuthenticate(authenticators)) {
            BiometricManager.BIOMETRIC_SUCCESS -> Unit
            BiometricManager.BIOMETRIC_ERROR_NONE_ENROLLED -> {
                error = "Configura un’impronta digitale o il blocco schermo nelle impostazioni del telefono."
                return
            }
            else -> { error = "Autenticazione sicura non disponibile. Controlla il blocco schermo."; return }
        }
        val signal = CancellationSignal()
        authCancel = signal
        authenticating = true
        error = ""
        val prompt = BiometricPrompt.Builder(this)
            .setTitle("NextDo")
            .setSubtitle("Sblocca l’applicazione")
            .setDescription("Usa l’impronta digitale o il metodo di blocco del telefono.")
            .setAllowedAuthenticators(authenticators)
            .setConfirmationRequired(false)
            .build()
        try {
            prompt.authenticate(signal, mainExecutor, object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    if (authCancel !== signal) return
                    authCancel = null
                    authenticating = false
                    finishDeviceUnlock()
                }
                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    if (authCancel !== signal) return
                    authCancel = null
                    authenticating = false
                    error = if (errorCode == BiometricPrompt.BIOMETRIC_ERROR_USER_CANCELED ||
                        errorCode == BiometricPrompt.BIOMETRIC_ERROR_CANCELED) "Sblocco annullato" else errString.toString()
                }
                override fun onAuthenticationFailed() {
                    // The system prompt remains open; never unlock on a failed match.
                }
            })
        } catch (e: Exception) {
            authCancel = null; authenticating = false
            error = "Impossibile avviare l’autenticazione Android"
        }
    }
    override fun onDestroy() {
        lockLocal()
        super.onDestroy()
    }
    private fun <T> task(work: () -> T, done: (T) -> Unit) {
        if (busy) return
        val started = epoch
        busy = true; error = ""
        lifecycleScope.launch {
            try {
                val result = withContext(Dispatchers.IO) { work() }
                if (started == epoch) done(result)
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) {
                if (started == epoch) error = when(e) {
                    is android.security.keystore.UserNotAuthenticatedException -> "Autenticazione telefono scaduta. Blocca e sblocca l’app."
                    else -> e.message?.take(250) ?: "Operazione non riuscita"
                }
            } finally { if (started == epoch) busy = false }
        }
    }
    private fun connect(base: String, code: String, replacing:Boolean=false) {
        if(offlineSyncBusy)return
        task({
            val a = TravelApi(base)
            val r = a.obj("/pair", data = JSONObject().put("code", code.trim()).put("label", "Android " + android.os.Build.MODEL.take(60)))
            val cfg = JSONObject().put("url", base.trim()).put("token", r.getString("device_token"))
            if(replacing){PrivateAlerts.disable(this);clearOfflineFiles()}
            vault.write("connection", cfg.toString().toByteArray())
            cfg
        }) { connection = it;travelAuthState=TravelAuthState.PIN_REQUIRED;if(replacing){offlineMeta=null;pendingZip=null;zipScope="";timelineFile=null;timelineScope="";timelineTrip=""} }
    }
    private fun unlockServer(pin: String) {
        val cfg = connection ?: return
        task({
            val api = TravelApi(cfg.getString("url"))
            val response = api.obj("/unlock", cfg.getString("token"), JSONObject().put("pin", pin).put("remember",true))
            val s = response.getString("session_token")
            val updated=JSONObject(cfg.toString())
            val remembered=response.optString("remember_token")
            if(remembered.isNotBlank()) {
                updated.put("remember_token",remembered)
                vault.write("connection",updated.toString().toByteArray())
            }
            Triple(s, api.trips(s),updated)
        }) { (s, list, updated) -> connection=updated;session = s; trips = list; offline = false;travelAuthState=TravelAuthState.CONNECTED }
    }
    private fun canEdit() = !locked && !offline && session.isNotBlank() && current?.revision?.let { it >= 0 } == true
    private fun importZip() {
        val uri = pendingZip ?: return
        val cfg = connection ?: return
        val s = session
        if(s.isBlank() || zipScope != timelineOwner(cfg)) return
        task({
            val bytes = contentResolver.openInputStream(uri)?.use { readLimited(it, 32 * 1024 * 1024) }
                ?: error("Impossibile leggere lo ZIP")
            val api = TravelApi(cfg.getString("url"))
            val result = api.importZip(s, bytes)
            Pair(result.getString("id"), api.trips(s))
        }) { (_, list) -> pendingZip=null; trips=list }
    }
    private fun submitEditor(e: TravelEditor, values: JSONObject) {
        val cfg = connection ?: return
        val s = session
        if(s.isBlank() || offline || locked) return
        if(e.kind == "new") {
            task({
                val api=TravelApi(cfg.getString("url"))
                api.obj("/trips",s,values)
                api.trips(s)
            }) { list -> trips=list; editor=null }
        } else {
            val t=current ?: return
            if(t.revision != e.revision || t.id != e.tripId) { error="Ricarica il viaggio";return }
            val payload=JSONObject().put("revision",e.revision).put("kind",e.kind).put("fields",values)
            if(e.kind=="booking"){
                values.remove("_template_id")?.let{payload.put("template_id",it)}
                values.remove("_specific_fields")?.let{payload.put("specific_fields",it)}
            }
            e.target.keys().forEach { k -> payload.put(k,e.target.get(k)) }
            task({
                val api=TravelApi(cfg.getString("url"))
                val r=api.obj("/trips/"+segment(t.id)+"/edit",s,payload)
                TripPackage(r.getJSONObject("manifest"),r.getJSONObject("state"),emptyMap(),r.getInt("revision"),templates=bookingCatalog(r.optJSONArray("templates"))) to api.trips(s)
            }) { (updated,list) -> current=updated;trips=list;editor=null }
        }
    }
    private fun edit(kind:String, data:JSONObject, target:JSONObject=JSONObject()) {
        val t=current ?: return
        if(!canEdit())return
        if(kind!="booking"){editor=TravelEditor(kind,t.id,t.revision,data,target);return}
        val cfg=connection?:return;val s=session
        task({
            try{bookingCatalog(TravelApi(cfg.str("url")).obj("/booking-templates",s).optJSONArray("templates"))}
            catch(e:TravelHttpException){if(e.status==404)emptyList() else throw e}
        }){catalog->
            if(current?.id==t.id){current=current?.copy(templates=catalog);editor=TravelEditor(kind,t.id,t.revision,data,target,catalog)}
        }
    }
    private fun selectTrip(id: String) {
        val cfg = connection ?: return
        val s = session
        task({
            val r = TravelApi(cfg.getString("url")).obj("/trips/" + segment(id), s)
            TripPackage(r.getJSONObject("manifest"), r.optJSONObject("state") ?: JSONObject(), emptyMap(), r.getInt("revision"),templates=bookingCatalog(r.optJSONArray("templates")))
        }) { openTrip(it, false) }
    }
    private fun openTrip(t: TripPackage, cached: Boolean) {
        area=NextDoArea.TRIPS; current = t; offline = cached; section = "Home"; updateCaptureProtection()
        selectedDay = t.days.firstOrNull { it.str("date") >= LocalDate.now().toString() }?.str("date")
            ?: t.days.firstOrNull()?.str("date").orEmpty()
    }
    private fun syncOffline(id:String,manual:Boolean=false,replace:Boolean=false) {
        val cfg=connection?:return
        val s=session
        if(locked||!foreground||s.isBlank()||busy||offlineSyncBusy||editor!=null||pdf!=null)return
        val previous=offlineMeta
        if(!manual&&previous?.str("id")!=id)return
        if(previous!=null&&previous.str("id")!=id&&!replace)return
        val owner=timelineOwner(cfg)
        val started=epoch;val generation=++offlineSyncGeneration
        offlineSyncBusy=true;offlineSyncStatus="Controllo aggiornamenti…"
        lifecycleScope.launch {
            try {
                val result=withContext(Dispatchers.IO){
                    val api=TravelApi(cfg.str("url"))
                    if(!manual){
                        val remote=api.obj("/trips/"+segment(id)+"/offline-state?include_catalog=true",s)
                        require(remote.str("id")==id&&remote.optInt("revision",-1)>=0){"Versione server non valida"}
                        if(!requiresOfflineDownload(previous?.str("snapshot").orEmpty(),remote.str("snapshot")))return@withContext null
                    }
                    val downloaded=OfflineSnapshot.download(api,s,id,owner,requireVersion=!manual)
                    val encoded=downloaded.encode()
                    synchronized(offlineGuard){
                        // Reject a late result after app lock, logout or a new device association.
                        require(started==epoch){"Sessione locale scaduta"}
                        val storedCfg=JSONObject(String(vault.read("connection"),Charsets.UTF_8))
                        require(timelineOwner(storedCfg)==owner){"Associazione cambiata"}
                        // Archive and metadata are one encrypted AtomicFile, never two independent writes.
                        vault.write(OFFLINE_FILE,encoded)
                        // Keep legacy files until the new atomic write has fully succeeded.
                        vault.remove("offline");vault.remove("offline_meta")
                    }
                    downloaded.meta
                }
                if(started==epoch&&generation==offlineSyncGeneration&&!locked&&session==s){
                    if(result!=null)offlineMeta=result
                    offlineLastChecked=java.time.OffsetDateTime.now().toString()
                    offlineSyncStatus=if((result?:previous)?.str("snapshot").orEmpty().isBlank())"Copia salvata; controllo versione non supportato dal server" else "Copia aggiornata"
                }
            }catch(e:CancellationException){throw e}
            catch(e:Exception){
                if(started==epoch&&generation==offlineSyncGeneration&&!locked){
                    offlineSyncStatus=when(e){
                        is TravelHttpException->if(e.status==401)"Autorizzazione scaduta: riconnetti NextDo. Copia precedente conservata." else "Controllo non riuscito (HTTP ${e.status}). Copia precedente conservata."
                        else->"Aggiornamento non riuscito. L’eventuale copia precedente è conservata."
                    }
                }
            }finally{if(started==epoch&&generation==offlineSyncGeneration)offlineSyncBusy=false}
        }
    }
    private fun downloadTrip(replace:Boolean=false) {
        val t=current?:return
        syncOffline(t.id,manual=true,replace=replace)
    }
    private fun openOffline() {
        val cfg=connection?:return
        val legacySaved=offlineMeta?.str("saved").orEmpty()
        task({
            val (modern,raw)=synchronized(offlineGuard){
                if(vault.exists(OFFLINE_FILE))true to vault.read(OFFLINE_FILE) else false to vault.read("offline")
            }
            if(modern){
                val snapshot=OfflineSnapshot.decode(raw,timelineOwner(cfg))
                snapshot.trip() to snapshot.meta.str("saved")
            }else TripPackage.parse(raw) to legacySaved
        }) { (trip,saved) -> offlineOpenedStamp=saved;openTrip(trip,true) }
    }
    private fun forget() {
        if(offlineSyncBusy)return
        PrivateAlerts.disable(this);privateAlertsEnabled=false
        timelineFile=null;timelineTrip="";timelineScope=""
        pendingZip=null;zipScope=""
        task({ synchronized(offlineGuard){vault.clear()} }) { lockLocal() }
    }
    private fun viewPdf(name: String) {
        val t = current ?: return
        val cfg = connection
        val s = session
        val cached = offline
        task({
            val bytes = if(cached) t.docs[name] ?: error("PDF non disponibile offline") else {
                require(cfg != null && s.isNotBlank()) { "Sblocca NextDo" }
                TravelApi(cfg.getString("url")).call("/trips/" + segment(t.id) + "/documents/" + segment(name), s)
            }
            val image = renderPage(bytes, 0)
            Triple(bytes, image.first, image.second)
        }) { (bytes, count, bmp) -> pdf = bytes; pdfName = name; pdfMessage = ""; pageCount = count; pageBitmap = bmp }
    }
    private fun renderPage(bytes: ByteArray, index: Int): Pair<Int,Bitmap> {
        val tmp = File.createTempFile("travel-pdf-", ".pdf", cacheDir)
        try {
            tmp.writeBytes(bytes)
            val fd = ParcelFileDescriptor.open(tmp, ParcelFileDescriptor.MODE_READ_ONLY)
            tmp.delete()
            PdfRenderer(fd).use { renderer ->
                require(index in 0 until renderer.pageCount)
                renderer.openPage(index).use { p ->
                    val scale = minOf(2200f / p.width, 3000f / p.height, 4.0f)
                    val bmp = Bitmap.createBitmap(maxOf(1,(p.width*scale).toInt()), maxOf(1,(p.height*scale).toInt()), Bitmap.Config.ARGB_8888)
                    bmp.eraseColor(android.graphics.Color.WHITE)
                    p.render(bmp, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                    return renderer.pageCount to bmp
                }
            }
        } finally { tmp.delete() }
    }
    private fun exportPdf(action: String) {
        val bytes = pdf ?: return
        val name = pdfName
        if (locked || busy) return
        pdfMessage = ""
        if (action == "download") {
            task({ PdfExport.download(this, name, bytes) }) { pdfMessage = "PDF salvato in Download/NextDo." }
        } else {
            task({ PdfExport.externalCopy(this, name, bytes) }) { uri ->
                try {
                    val intent = if (action == "share") Intent(Intent.ACTION_SEND).setType("application/pdf").putExtra(Intent.EXTRA_STREAM, uri)
                    else Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/pdf")
                    intent.clipData = android.content.ClipData.newRawUri("PDF", uri)
                    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    startActivity(Intent.createChooser(intent, if (action == "share") "Condividi PDF" else "Apri PDF con"))
                } catch (_: Exception) { error = "Nessuna applicazione compatibile disponibile." }
            }
        }
    }
    private fun launchExternal(url:String,maps:Boolean=false){
        try {
            val intent=Intent(Intent.ACTION_VIEW,Uri.parse(url))
            if(maps)try{startActivity(Intent(intent).setPackage("com.google.android.apps.maps"));return}catch(_:Exception){}
            startActivity(intent)
        }catch(_:Exception){error="Applicazione esterna non disponibile"}
    }
    private fun openAssistant(){
        if(locked)return
        val w=workConnection;val travel=connection;val token=session
        if(w==null&&(travel==null||token.isBlank())){error="Collega NextDo online; il link Work si imposta sul web.";return}
        task({
            if(w!=null)TravelApi(w.str("url")).obj("/work/assistant-link",w.str("token"))
            else TravelApi(travel!!.str("url")).obj("/assistant-link",token)
        }){result->
            val link=result.str("url")
            if(link.isBlank()){error="Configura la conversazione ChatGPT Work nelle Impostazioni web di NextDo.";return@task}
            val uri=Uri.parse(link)
            if(uri.scheme=="https"&&uri.encodedAuthority=="chatgpt.com"&&uri.query==null&&uri.fragment==null)launchExternal(link)
            else error="Collegamento ChatGPT non valido"
        }
    }
    private fun mapQuery(b:JSONObject):String {
        val lat = b.optDouble("lat"); val lon = b.optDouble("lon")
        return when {
            lat.isFinite() && lon.isFinite() && lat in -90.0..90.0 && lon in -180.0..180.0 -> "$lat,$lon"
            b.str("address").isNotBlank() -> b.str("address")
            else -> b.str("place")
        }
    }
    private fun navigate(b:JSONObject,directions:Boolean=false){
        val q=mapQuery(b);val explicit=b.str("map")
        val url=when {
            q.isNotBlank()&&directions -> "https://www.google.com/maps/dir/?api=1&destination="+Uri.encode(q)+"&dir_action=navigate"
            q.isNotBlank() -> "https://www.google.com/maps/search/?api=1&query="+Uri.encode(q)
            !directions&&explicit.startsWith("https://") -> explicit
            else -> return
        }
        launchExternal(url,q.isNotBlank())
    }
    @Composable private fun MapActions(b:JSONObject){
        if(mapQuery(b).isNotBlank()||b.str("map").startsWith("https://"))Row(horizontalArrangement=Arrangement.spacedBy(4.dp)){
            TextButton(onClick={navigate(b)}){Text("Apri in Maps")}
            if(mapQuery(b).isNotBlank())TextButton(onClick={navigate(b,true)}){Text("Naviga")}
        }
    }
    private fun closePdf() { pdf = null; pdfName = ""; pageBitmap = null; pageCount = 0; pdfMessage = "" }

    private fun <T> workTask(run:()->T,done:(T)->Unit){
        if(locked||workBusy)return
        val started=epoch
        workBusy=true;workError=""
        lifecycleScope.launch {
            try {
                val value=withContext(Dispatchers.IO){run()}
                if(started==epoch&&!locked)done(value)
            } catch(e:CancellationException){throw e}
            catch(e:Exception){if(started==epoch&&!locked){workAgenda=null;workDetail=null;workError=e.message?.take(200)?:"Connessione professionale non riuscita"}}
            finally{if(started==epoch)workBusy=false}
        }
    }
    private fun pairWork(url:String,code:String){
        workTask({
            val cfg=WorkApi(url).pair(code)
            vault.write("work_connection",cfg.toString().toByteArray())
            cfg
        }){workConnection=it;workAgenda=null;refreshAlertStatus()}
    }
    private fun refreshWork(){
        val cfg=workConnection?:return
        workTask({WorkApi(cfg.getString("url")).agenda(cfg.getString("token"))}){workAgenda=it}
    }
    private fun ackWork(id:Long,revision:String){
        val cfg=workConnection?:return
        workTask({
            val api=WorkApi(cfg.getString("url"))
            api.acknowledge(cfg.getString("token"),id,revision)
            WorkAlerts.kick(this)
            api.agenda(cfg.getString("token"))
        }){workAgenda=it}
    }
    private fun reviewWork(detail:JSONObject,action:String){
        val cfg=workConnection?:return
        if(workBusy)return
        workTask({
            val api=WorkApi(cfg.getString("url"))
            api.review(cfg.getString("token"),detail.getLong("id"),detail.str("revision"),action)
            WorkAlerts.kick(this)
            api.agenda(cfg.getString("token"))
        }){workAgenda=it;workDetail=null}
    }
    private fun loadWorkDetail(id:Long){
        val cfg=workConnection?:return
        workTask({WorkApi(cfg.getString("url")).detail(cfg.getString("token"),id)}){if(area==NextDoArea.WORK||area==NextDoArea.HOME)workDetail=it}
    }
    private fun disconnectWork(){
        val cfg=workConnection?:return
        workTask({
            WorkAlerts.disable(this)
            val revoked=try{WorkApi(cfg.getString("url")).revoke(cfg.getString("token"));true}catch(_:Exception){false}
            vault.remove("work_connection")
            revoked
        }){revoked->workConnection=null;workAgenda=null;workDetail=null;refreshAlertStatus();workError=if(revoked)"" else "Dati locali rimossi. Revoca il dispositivo anche dal web."}
    }
    private fun openArea(next:NextDoArea) {
        if(locked || busy) return
        closePdf(); current=null; editor=null; offline=false; section="Home"; error=""
        area=next
        if(next!=NextDoArea.PERSONAL)privateSection=""
        if(next==NextDoArea.WORK)workFilter="all"
        workDetail=null;updateCaptureProtection()
    }
    private fun backArea() {
        if(busy)return
        when {
            pdf!=null -> closePdf()
            current!=null -> openArea(NextDoArea.TRIPS)
            area==NextDoArea.TRIPS -> openArea(NextDoArea.PERSONAL)
            area==NextDoArea.PERSONAL&&privateSection.isNotBlank() -> {privateSection=""}
            area!=NextDoArea.HOME -> openArea(NextDoArea.HOME)
        }
    }
    @Composable private fun App() {
        // Only while the app is unlocked and visible; never introduce a background travel credential.
        LaunchedEffect(locked,foreground,session,offlineMeta?.str("id"),area){
            if(!locked&&foreground&&offlineMeta!=null&&connection!=null){
                while(true){
                    if(!busy&&!offlineSyncBusy&&editor==null&&pdf==null){
                        val id=offlineMeta?.str("id").orEmpty()
                        if(session.isNotBlank()&&id.isNotBlank())syncOffline(id)
                        else if(travelAuthState==TravelAuthState.RETRY&&connection?.str("remember_token").orEmpty().isNotBlank())retryServer()
                    }
                    kotlinx.coroutines.delay(60000)
                }
            }
        }
        LaunchedEffect(locked,area,session){
            if(!locked&&area==NextDoArea.PERSONAL&&session.isNotBlank()){
                val cfg=connection
                val s=session
                val started=epoch
                if(cfg!=null)try{
                    val values=withContext(Dispatchers.IO){TravelApi(cfg.getString("url")).obj("/items",s).arr("items")}
                    if(started==epoch&&!locked&&session==s){privateAgenda=values;privateProblem=""}
                }catch(e:CancellationException){throw e}catch(_:Exception){if(started==epoch&&!locked){privateAgenda=null;privateProblem="Agenda personale non disponibile"}}
            }
        }
        LaunchedEffect(locked,area,session,connection){
            if(!locked&&area==NextDoArea.PERSONAL&&session.isNotBlank()){
                val cfg=connection
                val s=session
                val started=epoch
                if(cfg!=null){
                    try {
                        val pref=withContext(Dispatchers.IO){TravelApi(cfg.getString("url")).obj("/appearance",s)}
                        if(started==epoch&&!locked&&session==s){personalAppearance=pref;appearanceError=""}
                    }catch(e:CancellationException){throw e}
                    catch(_:Exception){if(started==epoch&&!locked){appearanceError="Personalizzazione non disponibile. Verifica il collegamento a NextDo."}}
                }
            }
        }
        LaunchedEffect(locked,area,workConnection){
            if(!locked&&(area==NextDoArea.HOME||area==NextDoArea.WORK)&&workConnection!=null){
                while(true){refreshWork();kotlinx.coroutines.delay(30000)}
            }
        }
        val t = current
        BackHandler(enabled=!locked&&(t!=null||area!=NextDoArea.HOME||pdf!=null)){backArea()}
        if(!locked && (area==NextDoArea.WORK||area==NextDoArea.HOME)) workDetail?.let { detail -> WorkDetailDialog(detail,workBusy,{d->navigate(detail,d)},{action->reviewWork(detail,action)}){workDetail=null} }
        if(!locked && pdf != null) {
            PdfScreen()
            return
        }
        if(!locked) editor?.let { e -> TravelEditDialog(e,busy,error,{editor=null;error=""},{submitEditor(e,it)}) }
        Scaffold(containerColor = Navy,
            topBar = {
                Surface(color = Navy) {
                    Row(Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal=18.dp, vertical=12.dp), verticalAlignment=Alignment.CenterVertically) {
                        Box(Modifier.size(42.dp).clip(RoundedCornerShape(14.dp)).background(Teal), contentAlignment=Alignment.Center) {
                            Icon(Icons.Default.DoneAll, contentDescription=null, tint=Navy)
                        }
                        Spacer(Modifier.width(10.dp))
                        Column(Modifier.weight(1f)) {
                            Text("NextDo", color=White, fontWeight=FontWeight.ExtraBold, fontSize=20.sp)
                            Text(if(locked) "ACCESSO PROTETTO" else area.subtitle, color=if(area==NextDoArea.WORK&&!locked) Color(0xFF83B6FF) else Teal, fontSize=10.sp, fontWeight=FontWeight.Bold)
                        }
                        if (!locked && (t!=null || area!=NextDoArea.HOME)) IconButton(onClick={backArea()},enabled=!busy) { Icon(Icons.Default.ArrowBack,"Indietro") }
                        if (!locked) IconButton(onClick={lockLocal()}) { Icon(Icons.Default.Lock,"Blocca") }
                    }
                }
            },
            bottomBar = {
              Column {
                if(!locked && pdf==null)Surface(color=Panel){
                    TextButton(onClick={openAssistant()},enabled=!busy,modifier=Modifier.fillMaxWidth()){Text("ChatGPT Work",color=Teal)}
                }
                if(t != null && !locked && pdf == null) NavigationBar(containerColor=Panel) {
                    listOf("Home","Oggi","Prenota","PDF","Guide","Diario").forEach { label ->
                        val image = when(label) {
                            "Home" -> Icons.Default.Home
                            "Oggi" -> Icons.Default.CalendarToday
                            "Prenota" -> Icons.Default.ConfirmationNumber
                            "PDF" -> Icons.Default.Folder
                            "Diario" -> Icons.Default.Place
                            else -> Icons.Default.Book
                        }
                        NavigationBarItem(selected=section==label,onClick={section=label},enabled=!busy,icon={Icon(image,label)},label={Text(label,fontSize=11.sp)},
                            colors=NavigationBarItemDefaults.colors(indicatorColor=Teal.copy(alpha=.20f),selectedIconColor=Teal,selectedTextColor=Teal,unselectedIconColor=Muted,unselectedTextColor=Muted))
                    }
                } else if(!locked && pdf==null) NextDoNavigation(area,!busy){openArea(it)}
              }
            }) { padding ->
            val scroll=key(area,t?.id,section,pdf!=null){rememberScrollState()}
            Column(Modifier.fillMaxSize().padding(padding).verticalScroll(scroll).padding(16.dp), verticalArrangement=Arrangement.spacedBy(14.dp)) {
                UpdatePanel()
                if (busy) LinearProgressIndicator(Modifier.fillMaxWidth(), color=Teal)
                if (error.isNotBlank()) Card(colors=CardDefaults.cardColors(containerColor=Color(0xFF432E37))) {
                    Row(Modifier.padding(14.dp),verticalAlignment=Alignment.CenterVertically) {
                        Text(error,Modifier.weight(1f),color=White,fontSize=13.sp)
                        TextButton(onClick={error=""}) { Text("Chiudi") }
                    }
                }
                when {
                    locked -> LockedScreen()
                    t != null -> {
                        if (offline) Pill("OFFLINE · copia scaricata",Sand)
                        when(section) {
                            "Home" -> {
                                if(canEdit()) Action("Modifica dati viaggio",!busy){edit("trip",t.info)}
                                Home(t)
                            }
                            "Oggi" -> DayScreen(t)
                            "Prenota" -> BookingScreen(t)
                            "PDF" -> Documents(t)
                            "Guide" -> Guides(t)
                            "Diario" -> TimelineScreen(t)
                        }
                    }
                    area==NextDoArea.TRIPS -> ConnectionScreen()
                    area==NextDoArea.WORK -> WorkScreen(workConnection!=null,workAgenda,workBusy,workError,connection?.str("url").orEmpty(),{url,code->pairWork(url,code)},{refreshWork()},{id->loadWorkDetail(id)},{disconnectWork()},{id,rev->ackWork(id,rev)},workFilter)
                    area==NextDoArea.PERSONAL -> {
                        if(privateSection.isBlank())PersonalLanding(
                            !busy,personalAppearance,session.isNotBlank()&&personalAppearance!=null,appearanceError,
                            appearancePhoto!=null&&connection?.let{timelineOwner(it)==appearancePhotoOwner}==true,
                            {savePersonalAppearance(it)},{chooseAppearancePhoto()},{uploadAppearancePhoto()},
                            privateAgenda,{privateSection=it},privateAlertsEnabled,{togglePrivateAlerts()}, {connection?.str("url")?.takeIf{it.isNotBlank()}?.let{launchExternal(it)}}){openArea(NextDoArea.TRIPS)}
                        else PrivateAgendaScreen(privateSection,privateAgenda,personalAppearance,session.isNotBlank()&&!busy,privateProblem,{privateSection=""},{refreshPrivateAgenda()},{id,body->savePrivateItem(id,body)},{id->deletePrivateItem(id)})
                    }
                    area==NextDoArea.SETTINGS -> SettingsLanding()
                    else -> NextDoDashboard(!busy,session.isNotBlank(),offlineMeta!=null,workAgenda,workConnection!=null,workBusy,workError,{filter->openArea(NextDoArea.WORK);workFilter=filter},{id->loadWorkDetail(id)},{refreshWork()}){openArea(it)}
                }
                Spacer(Modifier.height(12.dp))
            }
        }
    }
    private fun enableWorkAlerts(){
        val cfg=workConnection?:return
        if(!WorkAlerts.permission(this)){alertPermission=false;return}
        workTask({
            val result=TravelApi(cfg.getString("url")).obj("/work/alerts/enable",cfg.getString("token"),JSONObject())
            WorkAlerts.enable(this,cfg.getString("url"),result.getString("alert_token"),result.getDouble("expires").toLong())
        }){refreshAlertStatus()}
    }
    private fun disableWorkAlerts(){
        val cfg=workConnection
        workTask({
            WorkAlerts.disable(this)
            if(cfg!=null)try{TravelApi(cfg.getString("url")).obj("/work/alerts/disable",cfg.getString("token"),JSONObject());true}catch(_:Exception){false} else false
        }){revoked->refreshAlertStatus();if(!revoked)workError="Avvisi locali disattivati. Per revocare la credenziale sul server, disassocia il dispositivo dal web."}
    }
    @Composable private fun SettingsLanding() {
        Text("Impostazioni",fontSize=26.sp,fontWeight=FontWeight.ExtraBold)
        TravelCard("Applicazione","NextDo "+packageManager.getPackageInfo(packageName,0).versionName) {
            Text("Un’unica app · aree separate",color=Muted)
            Action("Verifica aggiornamenti",!updateBusy&&!busy){checkUpdates(true)}
        }
        TravelCard("Assistente ChatGPT Work","Un’unica conversazione, configurata nelle impostazioni web dello stesso account.") {
            val base=workConnection?.str("url")?:connection?.str("url")
            if(!base.isNullOrBlank())Action("Configura sul web",!busy){launchExternal(base)}
            Text("L’accesso a Work richiede Internet. Non vengono trasferiti PIN, documenti o credenziali.",color=Muted,fontSize=12.sp)
        }
        TravelCard("Sicurezza","Accesso protetto dal dispositivo; blocco in background e dopo cinque minuti.") {
            Action("Blocca applicazione",!busy){lockLocal()}
            if(android.os.Build.VERSION.SDK_INT>=33){
                Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
                    Column(Modifier.weight(1f)){
                        Text("Consenti screenshot in Home e Lavoro")
                        Text("Le catture possono contenere dati riservati.",color=Muted,fontSize=12.sp)
                    }
                    Switch(checked=allowWorkScreenshots,onCheckedChange={allowWorkScreenshots=it;getPreferences(MODE_PRIVATE).edit().putBoolean("allow_work_screenshots",it).apply();updateCaptureProtection()})
                }
                Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
                    Column(Modifier.weight(1f)){
                        Text("Consenti screenshot in Personale")
                        Text("Consente le catture nella pagina personale.",color=Muted,fontSize=12.sp)
                    }
                    Switch(checked=allowPersonalScreenshots,onCheckedChange={allowPersonalScreenshots=it;getPreferences(MODE_PRIVATE).edit().putBoolean("allow_personal_screenshots",it).apply();updateCaptureProtection()})
                }
                Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
                    Column(Modifier.weight(1f)){
                        Text("Consenti screenshot in Viaggi")
                        Text("Attiva solo se necessario: le catture possono contenere prenotazioni e documenti riservati.",color=Muted,fontSize=12.sp)
                    }
                    Switch(checked=allowTravelScreenshots,onCheckedChange={allowTravelScreenshots=it;getPreferences(MODE_PRIVATE).edit().putBoolean("allow_travel_screenshots",it).apply();updateCaptureProtection()})
                }
                Text("Schermata bloccata, impostazioni e anteprime delle app recenti restano protette.",color=Muted,fontSize=12.sp)
            } else Text("Screenshot protetti su Android 12 e precedenti per tutelare le anteprime delle app recenti.",color=Muted,fontSize=12.sp)
        }
        TravelCard("Associazioni","Il collegamento Viaggi rimane distinto dall’autorizzazione professionale.") {
            Text(if(connection!=null)"Viaggi: dispositivo associato" else "Viaggi: non associato",color=Muted)
            Action("Gestisci connessione e archivio Viaggi",!busy){openArea(NextDoArea.TRIPS)}
            Text(if(workConnection!=null)"Professionale: associato" else "Professionale: non associato",color=Muted,fontSize=12.sp)
            Action("Gestisci agenda professionale",!busy){openArea(NextDoArea.WORK)}
        }
        TravelCard("Notifiche professionali","Avvisi generici, senza titoli o descrizioni. I promemoria funzionano anche con l’app chiusa, nei limiti di Android.") {
            if(workError.isNotBlank())Text(workError,color=Sand,fontSize=12.sp)
            Text(if(alertPermission)"Autorizzazione Android concessa" else "Autorizzazione Android mancante",color=Muted)
            if(!alertPermission)Action("Consenti notifiche",!workBusy){
                if(android.os.Build.VERSION.SDK_INT>=33&&checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=android.content.pm.PackageManager.PERMISSION_GRANTED)
                    notificationPermission.launch(android.Manifest.permission.POST_NOTIFICATIONS)
                else startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE,packageName))
            }
            Text(if(alertsEnabled)"Avvisi attivati" else "Avvisi disattivati",color=Teal,fontWeight=FontWeight.SemiBold)
            if(!alertsEnabled)Action("Attiva avvisi in background",workConnection!=null&&alertPermission&&!workBusy){enableWorkAlerts()}
            else {
                Text("Le notifiche critiche si ripetono fino alla presa visione sul telefono. La presa visione viene sincronizzata con il web e non completa l’attività.",fontSize=12.sp,color=Muted)
                Text("Gli allarmi critici possono essere silenziati senza confermare la presa visione.",fontSize=12.sp,color=Muted)
                Action("Disattiva avvisi",!workBusy){disableWorkAlerts()}
                TextButton(onClick={WorkAlerts.kick(this@MainActivity);refreshAlertStatus()}){Text("Sincronizza avvisi ora")}
            }
            Text("Scadenze: 24 ore prima e al termine. Appuntamenti con orario: anche 1 ora e 15 minuti prima. Se manca l’orario, promemoria alle 09:00 (fuso NextDo). Urgenze e voci da verificare segnalate anche senza data.",color=Muted,fontSize=12.sp)
            Text("Push Firebase se configurato e registrato; controllo periodico ogni 15 minuti come riserva. Il risparmio energetico può ritardare gli avvisi.",color=Sand,fontSize=12.sp)
            Text(if(WorkPush.active(this@MainActivity))"Push: registrato" else "Push: non ancora registrato (configura Firebase sul web e sincronizza gli avvisi).",fontSize=12.sp,color=Muted)
            val pending=WorkAlerts.pendingCount(this@MainActivity)
            if(pending>0)Text("Prese visione in attesa di sincronizzazione: "+pending,color=Sand,fontSize=12.sp)
            TextButton(onClick={startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE,packageName))}){Text("Suoni e vibrazione in Android")}
        }
        CriticalAlarmSettings()
    }
    @Composable private fun CriticalAlarmSettings(){
        TravelCard("Allarmi critici","Suono prolungato, ripetizione e schermata dedicata. Rispetta volume, canali e Non disturbare di Android.") {
            Text("Suoneria",fontWeight=FontWeight.Bold)
            Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){
                FilterChip(selected=alarmOptions.sound=="alarm",onClick={saveAlarmOptions(alarmOptions.copy(sound="alarm"))},label={Text("Sveglia")})
                FilterChip(selected=alarmOptions.sound=="siren",onClick={saveAlarmOptions(alarmOptions.copy(sound="siren"))},label={Text("Sirena")})
            }
            FilterChip(selected=alarmOptions.sound=="custom",onClick={
                try{ringtonePicker.launch(Intent(android.media.RingtoneManager.ACTION_RINGTONE_PICKER)
                    .putExtra(android.media.RingtoneManager.EXTRA_RINGTONE_TYPE,android.media.RingtoneManager.TYPE_ALARM)
                    .putExtra(android.media.RingtoneManager.EXTRA_RINGTONE_SHOW_SILENT,false)
                    .putExtra(android.media.RingtoneManager.EXTRA_RINGTONE_SHOW_DEFAULT,true)
                    .putExtra(android.media.RingtoneManager.EXTRA_RINGTONE_TITLE,"Suoneria allarme NextDo"))}
                catch(_:Exception){workError="Selettore suoneria non disponibile"}
            },label={Text("Scegli suoneria…")})
            Text("Durata del suono",fontWeight=FontWeight.Bold)
            Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){
                for(n in listOf(10,30,60))FilterChip(selected=alarmOptions.duration==n,onClick={saveAlarmOptions(alarmOptions.copy(duration=n))},label={Text("$n s")})
            }
            Text("Ripetizione fino alla presa visione",fontWeight=FontWeight.Bold)
            for(group in listOf(listOf(1,5,10),listOf(15,30,60))){
                Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){
                    for(n in group)FilterChip(selected=alarmOptions.repeat==n,onClick={saveAlarmOptions(alarmOptions.copy(repeat=n))},label={Text("$n min")})
                }
            }
            Row(verticalAlignment=Alignment.CenterVertically){
                Text("Vibrazione prolungata",Modifier.weight(1f));Switch(checked=alarmOptions.vibrate,onCheckedChange={saveAlarmOptions(alarmOptions.copy(vibrate=it))})
            }
            Row(verticalAlignment=Alignment.CenterVertically){
                Text("Schermata allarme e risveglio",Modifier.weight(1f));Switch(checked=alarmOptions.screen,onCheckedChange={saveAlarmOptions(alarmOptions.copy(screen=it))})
            }
            Row(verticalAlignment=Alignment.CenterVertically){
                Text("Notifica persistente",Modifier.weight(1f));Switch(checked=alarmOptions.persistent,onCheckedChange={saveAlarmOptions(alarmOptions.copy(persistent=it))})
            }
            if(android.os.Build.VERSION.SDK_INT>=34&&alarmOptions.screen&&!fullScreenAllowed){
                Text("Schermo intero non autorizzato: resta il banner Android.",color=Sand,fontSize=12.sp)
                Action("Consenti schermata allarme"){alarmSettings(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT)}
            }
            if(android.os.Build.VERSION.SDK_INT>=31&&!exactAlarmAllowed){
                Text("Allarmi esatti non autorizzati: la ripetizione può essere ritardata.",color=Sand,fontSize=12.sp)
                Action("Autorizza allarmi e promemoria"){alarmSettings(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM)}
            }
            Text("Se Android non consente l’audio prolungato in background, resta la notifica sonora normale. Gli intervalli sono indicativi in modalità risparmio energia.",color=Muted,fontSize=12.sp)
            Action("Prova allarme critico",alertPermission){WorkAlerts.test(this@MainActivity)}
            TextButton(onClick={startActivity(Intent(Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE,packageName).putExtra(Settings.EXTRA_CHANNEL_ID,CriticalAlarm.CHANNEL))}){Text("Impostazioni canale allarmi Android")}
        }
    }
    @Composable private fun UpdatePanel() {
        val update = availableUpdate
        if (update != null) {
            TravelCard("Aggiornamento disponibile", "NextDo " + update.version) {
                if (showUpdateNotes && update.notes.isNotBlank()) Text(update.notes, color=Muted, fontSize=13.sp)
                TextButton(onClick={showUpdateNotes=!showUpdateNotes}) { Text(if(showUpdateNotes) "Nascondi novità" else "Novità della versione") }
                Action(if(updateBusy) "Attendi…" else "Scarica e installa", !updateBusy && !busy) { installUpdate() }
            }
        }
        if (updateMessage.isNotBlank()) Text(updateMessage, color=Sand, fontSize=12.sp)
        if (updateBusy) LinearProgressIndicator(Modifier.fillMaxWidth(),color=Teal)
        if (locked || (current == null && area==NextDoArea.HOME)) TextButton(onClick={checkUpdates(true)}, enabled=!updateBusy) { Text("Verifica aggiornamenti") }
    }
    @Composable private fun Pill(text: String, color: Color=Teal) {
        Text(text, Modifier.clip(RoundedCornerShape(50)).background(color.copy(alpha=.14f)).padding(horizontal=12.dp, vertical=6.dp),
            color=color, fontSize=11.sp, fontWeight=FontWeight.SemiBold)
    }
    @Composable private fun TravelCard(title: String, subtitle: String="", content: @Composable ColumnScope.() -> Unit) {
        Card(Modifier.fillMaxWidth(),shape=RoundedCornerShape(22.dp),colors=CardDefaults.cardColors(containerColor=Panel)) {
            Column(Modifier.padding(17.dp),verticalArrangement=Arrangement.spacedBy(9.dp)) {
                Text(title,color=White,fontWeight=FontWeight.Bold,fontSize=18.sp)
                if(subtitle.isNotBlank()) Text(subtitle,color=Muted,fontSize=13.sp,lineHeight=19.sp)
                content()
            }
        }
    }
    @Composable private fun Action(text: String, enabled: Boolean=!busy, onClick: () -> Unit) {
        Button(onClick=onClick,enabled=enabled,shape=RoundedCornerShape(15.dp)) { Text(text,fontWeight=FontWeight.SemiBold) }
    }
    @Composable private fun TimelineScreen(t:TripPackage) {
        var saved by remember(t.id){mutableStateOf(t.timeline)}
        var loaded by remember(t.id){mutableStateOf(offline)}
        var from by remember(t.id){mutableStateOf(t.info.str("start"))}
        var to by remember(t.id){mutableStateOf(t.info.str("end"))}
        var preview by remember(t.id){mutableStateOf<JSONObject?>(null)}
        var result by remember(t.id){mutableStateOf("")}
        var confirm by remember{mutableStateOf(false)}
        val cfg=connection
        val file=timelineFile?.takeIf{cfg!=null&&timelineTrip==t.id&&timelineScope==timelineOwner(cfg)}
        LaunchedEffect(t.id,offline) {
            if(!offline && cfg!=null && session.isNotBlank()) {
                val s=session
                task({TravelApi(cfg.getString("url")).obj("/trips/"+segment(t.id)+"/timeline",s)}){saved=it.optJSONObject("data");loaded=true}
            }
        }
        val mapLoader:((Int,Int,Int,(Bitmap)->Unit)->Unit)?=if(!offline && cfg!=null && session.isNotBlank()) { z,x,y,done ->
            val s=session
            task({ val raw=TravelApi(cfg.getString("url")).call("/trips/"+segment(t.id)+"/timeline/map/$z/$x/$y",s,limit=4*1024*1024);BitmapFactory.decodeByteArray(raw,0,raw.size) ?: error("Mappa non valida") }){done(it)}
        } else null
        TravelCard("Cronologia salvata",if(offline) "Copia offline: aggiorna il download per le ultime modifiche." else "Storico privato sul Raspberry") {
            if(!offline && cfg!=null) Action("Aggiorna diario",!busy&&session.isNotBlank()) {
                val s=session;task({TravelApi(cfg.getString("url")).obj("/trips/"+segment(t.id)+"/timeline",s)}){saved=it.optJSONObject("data");loaded=true}
            }
            if(!loaded) Text("Caricamento o storico non ancora disponibile",color=Muted)
            DiaryViewer(t,saved,mapLoader,busy)
        }
        if(offline)return
        TravelCard("Diario di bordo","Importa la cronologia esportata da Google Maps. Nessuna registrazione GPS aggiuntiva.") {
            DateField("Dal",from,{from=it;preview=null},enabled=!busy)
            DateField("Al (incluso)",to,{to=it;preview=null},enabled=!busy)
            Text("Le date seguono il fuso presente nei singoli eventi di Google. Gli eventi a cavallo dei limiti vengono esclusi; i punti del percorso vengono filtrati singolarmente.",color=Muted,fontSize=12.sp)
            Action("Scegli file JSON",!busy&&cfg!=null){
                preview=null;timelineFile=null;timelineTrip=t.id;timelineScope=timelineOwner(cfg!!)
                timelinePicker.launch("*/*")
            }
            Text(if(file!=null)"File selezionato. Puoi analizzarlo." else "Dopo la scelta del file, se richiesto, sblocca l’app e riapri questo viaggio e Diario.",color=Muted,fontSize=12.sp)
            Action("Analizza sul telefono",!busy&&file!=null){
                val uri=file ?: return@Action
                val a=from;val b=to
                preview=null;result=""
                task({
                    try{contentResolver.openInputStream(uri)?.use{TimelineImport.parse(it,a,b)}?:error("File non leggibile")}
                    catch(e:Exception){throw IllegalArgumentException(if(e is IllegalArgumentException)e.message?.takeIf{it in listOf("Intervallo non valido","Troppi dati: seleziona un periodo più breve","Formato Cronologia Google non supportato","Nessuno spostamento compatibile nell’intervallo","Archivio troppo grande")} ?: "File o date non validi" else "Impossibile leggere la cronologia")}
                }){preview=it}
            }
            preview?.let{p->
                val paths=p.getJSONArray("paths")
                val points=(0 until paths.length()).sumOf{paths.getJSONArray(it).length()}
                Text(ItalianDateTime.date(p.getString("from"))+" — "+ItalianDateTime.date(p.getString("to")),color=Teal)
                Text("Visite: "+p.getJSONArray("visits").length()+" · Spostamenti: "+p.getJSONArray("activities").length()+" · Punti: "+points)
                for(v in p.arr("visits").take(5))Text(ItalianDateTime.dateTime(v.str("startTime"),true)+" · "+v.getJSONObject("location").optDouble("lat")+", "+v.getJSONObject("location").optDouble("lon"),color=Muted,fontSize=12.sp)
                Text("Il file originale e gli altri periodi non vengono inviati. Un nuovo import sostituisce il diario precedente di questo viaggio.",color=Sand,fontSize=12.sp)
                Action("Conferma e sincronizza",!busy&&cfg!=null&&session.isNotBlank()){confirm=true}
            }
            if(result.isNotBlank())Text(result,color=Teal)
            if(confirm) AlertDialog(onDismissRequest={confirm=false},title={Text("Salvare la cronologia filtrata?")},text={Text("Il diario precedente di questo viaggio verrà sostituito. Il file originale non viene inviato.")},
                confirmButton={TextButton(onClick={
                    confirm=false;val p=preview;val c=connection;val s=session
                    if(p!=null&&c!=null&&s.isNotBlank())task({
                        require(p.toString().toByteArray(Charsets.UTF_8).size<=5*1024*1024){"Importazione troppo grande"}
                        TravelApi(c.getString("url")).obj("/trips/"+segment(t.id)+"/timeline",s,p)
                    }){preview=null;timelineFile=null;saved=p;loaded=true;result="Cronologia salvata."}
                }){Text("Salva")}},dismissButton={TextButton(onClick={confirm=false}){Text("Annulla")}})
        }
    }
    @Composable private fun LockedScreen() {
        Box(Modifier.fillMaxWidth().height(260.dp).clip(RoundedCornerShape(28.dp)).background(Brush.linearGradient(listOf(Color(0xFF1B5271),Color(0xFF163E4B),Panel))), contentAlignment=Alignment.Center) {
            Column(horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.spacedBy(12.dp)) {
                Icon(Icons.Default.Fingerprint,null,Modifier.size(64.dp),tint=Teal)
                Text("La tua organizzazione.",color=White,fontSize=26.sp,fontWeight=FontWeight.ExtraBold)
                Text("Professionale e personale, in un unico spazio.",color=Muted,fontSize=12.sp)
                Action("Sblocca NextDo",!busy&&!authenticating) { deviceUnlock() }
                Text("Impronta digitale o blocco schermo",color=Muted,fontSize=12.sp)
            }
        }
        Text("Accesso protetto da Android. Blocco automatico quando esci dall’app o dopo 5 minuti dallo sblocco. I dati Viaggi offline restano cifrati.",color=Muted,fontSize=13.sp)
    }
    @Composable private fun ConnectionScreen() {
        var url by remember { mutableStateOf("") }
        var code by remember { mutableStateOf("") }
        var pin by remember { mutableStateOf("") }
        var erase by remember { mutableStateOf(false) }
        var repairConfirm by remember { mutableStateOf(false) }
        var repairCode by remember { mutableStateOf("") }
        val cfg = connection
        Text("Viaggi",fontSize=26.sp,fontWeight=FontWeight.ExtraBold,color=White)
        if(cfg==null) {
            TravelCard("Collega NextDo","Da NextDo Web: Area personale → Viaggi → App Android. Genera un codice monouso.") {
                OutlinedTextField(url,{url=it},label={Text("URL HTTPS di NextDo")},singleLine=true,modifier=Modifier.fillMaxWidth())
                OutlinedTextField(code,{code=it},label={Text("Codice associazione")},singleLine=true,visualTransformation=PasswordVisualTransformation(),modifier=Modifier.fillMaxWidth())
                Action("Associa dispositivo",!busy&&url.isNotBlank()&&code.isNotBlank()) { val c=code;code="";connect(url,c) }
            }
        } else if(session.isBlank()) {
            when(travelAuthState) {
                TravelAuthState.PIN_REQUIRED -> TravelCard("Autorizza il telefono","Il PIN serve solo per la prima autorizzazione o se quella precedente non è più valida. Dopo basta lo sblocco Android.") {
                    OutlinedTextField(pin,{pin=it.filter(Char::isDigit).take(12)},label={Text("PIN NextDo (4–12 cifre)")},visualTransformation=PasswordVisualTransformation(),keyboardOptions=KeyboardOptions(keyboardType=KeyboardType.NumberPassword),singleLine=true)
                    Action("Autorizza",!busy&&pin.length in 4..12) { val p=pin;pin="";unlockServer(p) }
                }
                TravelAuthState.REPAIR_REQUIRED -> TravelCard("Associazione non più valida","Genera un nuovo codice di associazione dal Web. La copia offline già presente resta consultabile finché non la cancelli.") {
                    OutlinedTextField(code,{code=it},label={Text("Nuovo codice associazione")},singleLine=true,visualTransformation=PasswordVisualTransformation(),modifier=Modifier.fillMaxWidth())
                    Action("Associa nuovamente",!busy&&!offlineSyncBusy&&code.isNotBlank()) {
                        val c=code;code=""
                        // A replacement association may belong to a different account.
                        // Clear the prior offline copy only after an explicit confirmation.
                        repairCode=c
                        repairConfirm=true
                    }
                    if(repairConfirm)AlertDialog(onDismissRequest={repairConfirm=false;repairCode=""},title={Text("Rinnova associazione?")},text={Text("La copia offline precedente sarà rimossa dopo la nuova associazione riuscita, per non mescolare account. I viaggi sul server restano invariati.")},
                        confirmButton={TextButton(onClick={val c=repairCode;repairConfirm=false;repairCode="";connect(cfg.str("url"),c,true)}){Text("Conferma")}},dismissButton={TextButton(onClick={repairConfirm=false;repairCode=""}){Text("Annulla")}})
                }
                else -> TravelCard("Connessione automatica","Il telefono è già autorizzato. Non è necessario inserire nuovamente il PIN.") {
                    Action("Riprova connessione",!busy){retryServer()}
                    Text("Se sei senza rete, apri la copia offline qui sotto.",color=Muted,fontSize=12.sp)
                }
            }
        } else {
            Text("I tuoi viaggi",fontSize=26.sp,fontWeight=FontWeight.ExtraBold,color=White)
            Action("Nuovo viaggio", !busy) { editor=TravelEditor("new") }
            Action("Seleziona itinerario ZIP", !busy) {
                pendingZip=null
                zipScope=timelineOwner(cfg)
                zipPicker.launch(arrayOf("application/zip","application/x-zip-compressed","application/octet-stream"))
            }
            if(pendingZip!=null && zipScope==timelineOwner(cfg)) TravelCard("Itinerario selezionato","Il file verrà importato nel tuo archivio privato sul Raspberry. Un viaggio esistente non sarà sovrascritto.") {
                Action("Conferma importazione", !busy) { importZip() }
                TextButton(onClick={pendingZip=null},enabled=!busy){Text("Annulla")}
            }
            if(trips.isEmpty()) Text("Nessun viaggio disponibile",color=Muted)
            for (item in trips) TravelCard(item.str("title"),ItalianDateTime.date(item.str("start"))+"  —  "+ItalianDateTime.date(item.str("end"))) {
                Action("Apri viaggio") { selectTrip(item.str("id")) }
            }
            TextButton(onClick={session="";trips=emptyList();retryServer()},enabled=!busy&&!offlineSyncBusy) { Text("Riconnetti") }
        }
        offlineMeta?.let { meta ->
            TravelCard("Disponibile offline",meta.str("title")+" · "+meta.optInt("pdfs")+" PDF") {
                Pill("NESSUNA CONNESSIONE NECESSARIA")
                Text("Ultimo download: "+ItalianDateTime.dateTime(meta.str("saved")),color=Muted,fontSize=12.sp)
                OfflineSyncInfo()
                if(session.isNotBlank())Action("Controlla aggiornamenti",!busy&&!offlineSyncBusy){syncOffline(meta.str("id"))}
                Action("Apri copia offline") { openOffline() }
            }
        }
        if(offlineMeta==null&&offlineSyncStatus.isNotBlank())Text(offlineSyncStatus,color=Sand,fontSize=12.sp)
        if(cfg!=null || offlineMeta!=null) TextButton(onClick={erase=true},enabled=!busy&&!offlineSyncBusy) { Text("Disassocia e cancella dati locali",color=Sand) }
        if(erase) AlertDialog(onDismissRequest={erase=false},title={Text("Cancellare i dati locali?")},text={Text("La copia offline e l’associazione verranno eliminate. I viaggi su NextDo non saranno modificati. Revoca il dispositivo anche dal web.")},
            confirmButton={TextButton(onClick={erase=false;forget()}){Text("Cancella")}},dismissButton={TextButton(onClick={erase=false}){Text("Annulla")}})
    }
    @Composable private fun Hero(t: TripPackage) {
        val cover = t.manifest.optJSONObject("cover")?.str("jpeg").orEmpty()
        val bmp = remember(cover) { try { if(cover.isBlank()) null else Base64.decode(cover,Base64.DEFAULT).let { BitmapFactory.decodeByteArray(it,0,it.size) } } catch(_:Exception){null} }
        val info = t.info
        val countdown = try {
            val now=LocalDate.now(); val start=LocalDate.parse(info.str("start"));val end=LocalDate.parse(info.str("end"))
            when { now<start -> ChronoUnit.DAYS.between(now,start).toString()+" giorni alla partenza";now<=end -> "In viaggio";else -> "Viaggio concluso" }
        } catch(_:Exception) { "Il tuo viaggio" }
        Box(Modifier.fillMaxWidth().height(258.dp).clip(RoundedCornerShape(26.dp)).background(Brush.linearGradient(listOf(Color(0xFF245D78),Color(0xFF132D42),Color(0xFF91714B))))) {
            if(bmp!=null) Image(bmp.asImageBitmap(),null,Modifier.matchParentSize(),contentScale=ContentScale.Crop)
            Box(Modifier.matchParentSize().background(Brush.verticalGradient(listOf(Color.Transparent,Color(0xD90B1726)))))
            Column(Modifier.align(Alignment.BottomStart).padding(20.dp),verticalArrangement=Arrangement.spacedBy(7.dp)) {
                Pill(countdown,Sand)
                Text(info.str("title"),fontSize=32.sp,fontWeight=FontWeight.ExtraBold,color=White,lineHeight=34.sp)
                Text(info.str("subtitle"),color=White,fontSize=13.sp)
                Text(ItalianDateTime.date(info.str("start"))+" — "+ItalianDateTime.date(info.str("end")),color=Muted,fontSize=12.sp)
            }
        }
    }
    @Composable private fun OfflineSyncInfo(){
        if(offlineSyncBusy)LinearProgressIndicator(Modifier.fillMaxWidth())
        Text(offlineSyncStatus.ifBlank{if(session.isBlank())"Copia locale · non verificata online" else "Controllo automatico quando NextDo è raggiungibile"},color=Muted,fontSize=12.sp)
        if(offlineLastChecked.isNotBlank())Text("Ultimo controllo riuscito: "+ItalianDateTime.dateTime(offlineLastChecked),color=Muted,fontSize=12.sp)
    }
    @Composable private fun Home(t: TripPackage) {
        Hero(t)
        val policies=t.bookings.filter{b->bookingModel(b,t.templates).id=="insurance"||((b.str("kind").isBlank()||b.str("kind")=="other")&&inferBookingKind("",b.str("type"),emptyList())=="insurance")}
        if(policies.isNotEmpty())TravelCard("Assicurazione ed emergenze",if(offline)"Dati e documenti della copia offline" else "Polizze e recapiti salvati nel viaggio"){
            for(b in policies){
                Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(8.dp)){Icon(Icons.Default.Shield,null,tint=Teal);Text(b.str("title"),fontWeight=FontWeight.Bold)}
                if(b.str("ref").isNotBlank())Text("Riferimento: "+b.str("ref"),color=Sand)
                if(b.str("date").isNotBlank())Text(ItalianDateTime.temporalText(b.str("date")),color=Muted)
                for(key in listOf("lines","fields")){
                    val a=b.optJSONArray(key)?:continue
                    for(i in 0 until a.length())a.optJSONArray(i)?.let{pair->if(pair.optString(1).isNotBlank())Text(pair.optString(0)+": "+pair.optString(1),color=White,fontSize=13.sp)}
                }
                bookingDocuments(b).forEach{(name,label)->Action(label,!busy){viewPdf(name)}}
            }
            Text("Verifica i recapiti e la procedura nella polizza. NextDo mostra solo le informazioni salvate.",color=Muted,fontSize=12.sp)
            Action("Tutte le prenotazioni"){section="Prenota"}
        }
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(10.dp)) {
            Metric(t.days.size.toString(),"Giornate",Modifier.weight(1f)){section="Oggi"}
            Metric(t.bookings.size.toString(),"Prenotazioni",Modifier.weight(1f)){section="Prenota"}
            Metric(documentMap(t).size.toString(),"PDF",Modifier.weight(1f)){section="PDF"}
        }
        val next=t.days.firstOrNull{it.str("date")==selectedDay}
        TravelCard("La prossima tappa",next?.let { listOf(ItalianDateTime.date(it.str("date")),it.str("place"),it.str("headline")).filter{v->v.isNotBlank()}.joinToString(" · ") } ?: "Programma da definire") {
            Action("Vai all’itinerario") { section="Oggi" }
        }
        if(!offline) TravelCard("Porta il viaggio con te","Scarica itinerari, guide, foto e PDF in un unico archivio cifrato. Una sola copia offline alla volta.") {
            var replace by remember { mutableStateOf(false) }
            if(offlineMeta?.str("id")==t.id){
                Pill("COPIA OFFLINE PRESENTE")
                Text("Ultimo download: "+ItalianDateTime.dateTime(offlineMeta?.str("saved").orEmpty()),color=Muted,fontSize=12.sp)
            }
            OfflineSyncInfo()
            Action("Scarica / aggiorna offline",!busy&&!offlineSyncBusy) {
                if(offlineMeta!=null&&offlineMeta?.str("id")!=t.id)replace=true else downloadTrip()
            }
            if(replace) AlertDialog(onDismissRequest={replace=false},title={Text("Sostituire il viaggio offline?")},text={Text("La copia offline precedente sarà sostituita. L’archivio centrale non cambia.")},confirmButton={TextButton(onClick={replace=false;downloadTrip(true)}){Text("Sostituisci")}},dismissButton={TextButton(onClick={replace=false}){Text("Annulla")}})
        }
        else {
            Text("Copia offline in sola lettura. Si aggiorna automaticamente quando l’app è sbloccata e NextDo è raggiungibile.",color=Muted,fontSize=12.sp)
            OfflineSyncInfo()
            if(offlineMeta?.str("id")==t.id&&offlineMeta?.str("saved")!=offlineOpenedStamp)Action("Apri copia aggiornata",!busy&&!offlineSyncBusy){openOffline()}
            if(session.isNotBlank())Action("Controlla aggiornamenti",!busy&&!offlineSyncBusy){syncOffline(t.id)}
        }
    }
    @Composable private fun Metric(value:String,label:String,modifier:Modifier,onClick:()->Unit) {
        Column(modifier.clip(RoundedCornerShape(18.dp)).background(Panel).clickable(onClick=onClick).padding(12.dp),verticalArrangement=Arrangement.spacedBy(4.dp)) {
            Text(value,color=Teal,fontSize=25.sp,fontWeight=FontWeight.ExtraBold);Text(label,color=Muted,fontSize=11.sp)
        }
    }
    @Composable private fun DayScreen(t: TripPackage) {
        Text("Il tuo itinerario",fontSize=26.sp,fontWeight=FontWeight.ExtraBold)
        Row(Modifier.fillMaxWidth().heightIn(min=48.dp),verticalAlignment=Alignment.CenterVertically) {
            val i=t.days.indexOfFirst{it.str("date")==selectedDay}
            IconButton(onClick={if(i>0)selectedDay=t.days[i-1].str("date")},enabled=i>0){Icon(Icons.Default.ArrowBack,"Giorno precedente")}
            Text(ItalianDateTime.date(selectedDay).ifBlank{"Nessuna giornata"},Modifier.weight(1f),color=Teal,fontSize=19.sp,fontWeight=FontWeight.Bold)
            IconButton(onClick={if(i>=0&&i<t.days.lastIndex)selectedDay=t.days[i+1].str("date")},enabled=i>=0&&i<t.days.lastIndex){Icon(Icons.Default.ArrowForward,"Giorno successivo")}
        }
        val d=t.days.firstOrNull{it.str("date")==selectedDay}?:return
        if(canEdit()) {
            Action("Modifica giornata",!busy){edit("day",d,JSONObject().put("date",selectedDay))}
            Action("Aggiungi evento",!busy){edit("event",JSONObject(),JSONObject().put("date",selectedDay))}
        }
        TravelCard(d.str("headline").ifBlank{d.str("place").ifBlank{"Giornata"}},d.str("description")) {
            Photo(t.manifest.optJSONObject("travel_photos")?.optJSONObject("day:"+selectedDay))
            if(d.str("place").isNotBlank())Pill(d.str("place"))
            d.arr("route_points").forEach { point -> Location(point) }
        }
        for((eventIndex,e) in d.arr("events").withIndex()) {
            val booking=t.bookings.firstOrNull{it.str("id")==e.str("bid")}
            val guide=t.guides.firstOrNull{it.str("id")==e.str("gid")}
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(10.dp)) {
                Column(Modifier.width(55.dp),horizontalAlignment=Alignment.CenterHorizontally) {
                    Text(ItalianDateTime.temporalText(e.str("time")).ifBlank{"·"},color=Sand,fontSize=13.sp,fontWeight=FontWeight.Bold)
                    Box(Modifier.padding(top=6.dp).size(8.dp).clip(RoundedCornerShape(10.dp)).background(Teal))
                    Box(Modifier.padding(top=4.dp).width(2.dp).height(60.dp).background(Teal.copy(alpha=.3f)))
                }
                Column(Modifier.weight(1f)) {
                    TravelCard(e.str("title"),e.str("details")) {
                        if(canEdit()) TextButton(onClick={edit("event",e,JSONObject().put("date",selectedDay).put("index",eventIndex))},enabled=!busy){Text("Modifica evento")}
                        if(e.optBoolean("warning")) Pill("ATTENZIONE",Sand)
                        if(booking!=null) BookingActions(booking)
                        if(guide!=null && guide.str("doc").isNotBlank()) Action("PDF guida"){viewPdf(guide.str("doc"))}
                    }
                }
            }
        }
        val checks=d.optJSONArray("checks")
        if(checks!=null&&checks.length()>0)TravelCard("Checklist","Stato sincronizzato, in sola lettura") {
            val done=t.state.optJSONObject("checks")?.optJSONArray(selectedDay)
            for(i in 0 until checks.length()) {
                val checked=done!=null&&(0 until done.length()).any{done.optInt(it,-1)==i}
                Row(verticalAlignment=Alignment.CenterVertically) { Icon(if(checked)Icons.Default.CheckCircle else Icons.Default.RadioButtonUnchecked,null,tint=if(checked)Teal else Muted);Spacer(Modifier.width(8.dp));Text(checks.optString(i),fontSize=13.sp) }
            }
        }
        t.state.optJSONObject("notes")?.str(selectedDay)?.takeIf{it.isNotBlank()}?.let { TravelCard("Note della giornata",it){} }
    }
    @Composable private fun Photo(img:JSONObject?) {
        val raw=img?.str("jpeg").orEmpty()
        val bitmap=remember(raw){try{if(raw.isEmpty())null else Base64.decode(raw,Base64.DEFAULT).let{BitmapFactory.decodeByteArray(it,0,it.size)}}catch(_:Exception){null}}
        bitmap?.let { Image(it.asImageBitmap(),null,Modifier.fillMaxWidth().height(150.dp).clip(RoundedCornerShape(14.dp)),contentScale=ContentScale.Crop) }
        img?.str("credit")?.takeIf{it.isNotBlank()}?.let{Text(it,color=Muted,fontSize=10.sp)}
    }
    @Composable private fun Location(b:JSONObject) {
        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(9.dp)) {
            Icon(Icons.Default.Place,null,tint=Teal)
            Column(Modifier.weight(1f)) { Text(b.str("label").ifBlank{b.str("place")},fontWeight=FontWeight.SemiBold,color=White);Text(b.str("address"),color=Muted,fontSize=12.sp) }
        }
        MapActions(b)
    }
    private fun bookingDocuments(b:JSONObject):List<Pair<String,String>> {
        val docs=linkedMapOf<String,String>()
        val primary=b.str("doc")
        if(primary.isNotBlank())docs[primary]=b.str("doc_label").ifBlank{if(b.optBoolean("original"))"Documento originale" else "Documento già presente"}
        b.arr("attachments").forEach{a->
            val name=a.str("file")
            if(name.isNotBlank())docs.putIfAbsent(name,a.str("label").ifBlank{name})
        }
        return docs.entries.map{it.key to it.value}
    }
    @Composable private fun BookingActions(b:JSONObject) {
        bookingDocuments(b).forEach{(name,label)->Action(label){viewPdf(name)}}
        if(b.arr("locations").isNotEmpty())b.arr("locations").forEach{Location(it)}
        else MapActions(b)
    }
    @Composable private fun BookingScreen(t:TripPackage) {
        Text("Le tue prenotazioni",fontSize=26.sp,fontWeight=FontWeight.ExtraBold)
        if(canEdit()) Action("Aggiungi prenotazione",!busy){edit("booking",JSONObject())}
        for(b in t.bookings)TravelCard(b.str("title"),listOf(b.str("type"),ItalianDateTime.temporalText(b.str("date")),b.str("place")).filter{it.isNotBlank()}.joinToString(" · ")) {
            val model=bookingModel(b,t.templates)
            Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(8.dp)){
                Icon(bookingIcon(model.icon),null,tint=Teal);Text(model.label,color=Teal,fontWeight=FontWeight.SemiBold)
            }
            if(canEdit()) TextButton(onClick={edit("booking",b,JSONObject().put("id",b.str("id")))},enabled=!busy){Text("Modifica prenotazione")}
            Photo(t.manifest.optJSONObject("travel_photos")?.optJSONObject("booking:"+b.str("id")))
            if(b.str("status").isNotBlank())Pill(b.str("status"))
            if(b.str("ref").isNotBlank())Text("Riferimento: "+b.str("ref"),color=Sand,fontSize=13.sp)
            if(b.str("price").isNotBlank())Text(b.str("price"),color=Teal,fontWeight=FontWeight.Bold)
            for(key in listOf("lines","fields")) {
                val a=b.optJSONArray(key)?:continue
                for(i in 0 until a.length())a.optJSONArray(i)?.let{Text(it.optString(0)+": "+ItalianDateTime.fieldValue(it.optString(0),it.optString(1)),fontSize=13.sp,color=Muted)}
            }
            BookingActions(b)
        }
    }
    private fun documentMap(t:TripPackage):Map<String,String> {
        val docs=linkedMapOf<String,String>()
        t.guides.forEach{if(it.str("doc").isNotBlank())docs[it.str("doc")]=it.str("title")}
        t.manifest.arr("documents").forEach{if(it.str("file").isNotBlank())docs[it.str("file")]=it.str("title")}
        t.manifest.arr("expenses").forEach{if(it.str("doc").isNotBlank())docs[it.str("doc")]=it.str("title")}
        t.bookings.forEach{b->bookingDocuments(b).forEach{(name,label)->docs[name]=b.str("title")+" · "+label}}
        t.docs.keys.forEach{docs.putIfAbsent(it,it)}
        return docs
    }
    @Composable private fun Documents(t:TripPackage) {
        Text("Documenti e voucher",fontSize=26.sp,fontWeight=FontWeight.ExtraBold)
        if(offline)Pill("PDF DISPONIBILI OFFLINE")
        documentMap(t).forEach{(name,title)->
            TravelCard(title.ifBlank{name},name){Action("Visualizza PDF"){viewPdf(name)}}
        }
    }
    @Composable private fun Guides(t:TripPackage) {
        Text("Guide pratiche",fontSize=26.sp,fontWeight=FontWeight.ExtraBold)
        for(g in t.guides)TravelCard(g.str("title"),g.str("summary")){
            if(g.str("category").isNotBlank())Pill(g.str("category"))
            val a=g.optJSONArray("items")
            if(a!=null)for(i in 0 until a.length())a.optJSONArray(i)?.let{Text(it.optString(0)+": "+it.optString(1),fontSize=13.sp,color=Muted)}
            if(g.str("doc").isNotBlank())Action("Apri guida PDF"){viewPdf(g.str("doc"))}
        }
    }
    @Composable private fun PdfScreen() {
        val bytes = pdf ?: return
        key(bytes) {
            NextDoPdfViewer(window=window, name=pdfName, count=pageCount, firstPage=pageBitmap,
                render={index -> renderPage(bytes,index).second}, busy=busy, message=pdfMessage, error=error,
                onClose={if(!busy)closePdf()}, onExport={exportPdf(it)}, onDismissMessage={pdfMessage="";error=""})
        }
    }
}
