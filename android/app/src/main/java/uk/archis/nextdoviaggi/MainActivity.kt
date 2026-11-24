package uk.archis.nextdoviaggi

import android.app.Activity
import android.app.KeyguardManager
import android.os.Handler
import android.os.Looper
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.pdf.PdfRenderer
import android.net.Uri
import android.os.Bundle
import android.os.ParcelFileDescriptor
import android.util.Base64
import android.view.WindowManager
import androidx.activity.ComponentActivity
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
    private var authenticating by mutableStateOf(false)
    private var busy by mutableStateOf(false)
    private var error by mutableStateOf("")
    private var connection by mutableStateOf<JSONObject?>(null)
    private var session by mutableStateOf("")
    private var trips by mutableStateOf<List<JSONObject>>(emptyList())
    private var current by mutableStateOf<TripPackage?>(null)
    private var offline by mutableStateOf(false)
    private var offlineMeta by mutableStateOf<JSONObject?>(null)
    private var section by mutableStateOf("Home")
    private var selectedDay by mutableStateOf("")
    private var pdf by mutableStateOf<ByteArray?>(null)
    private var pdfName by mutableStateOf("")
    private var page by mutableStateOf(0)
    private var pageCount by mutableStateOf(0)
    private var pageBitmap by mutableStateOf<Bitmap?>(null)
    private var epoch = 0
    private val authHandler = Handler(Looper.getMainLooper())
    private val autoLock = Runnable { lockLocal() }
    private val authenticate = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (authenticating) {
            authenticating = false
            if (result.resultCode == Activity.RESULT_OK) finishDeviceUnlock()
            else error = "Sblocco annullato"
        }
    }
    private fun finishDeviceUnlock() {
        task({
            val cfg = if (vault.exists("connection")) JSONObject(String(vault.read("connection"), Charsets.UTF_8)) else null
            val meta = if (vault.exists("offline_meta")) JSONObject(String(vault.read("offline_meta"), Charsets.UTF_8)) else null
            Pair(cfg, meta)
        }) { (cfg, meta) ->
            connection = cfg; offlineMeta = meta; locked = false
            authHandler.removeCallbacks(autoLock)
            authHandler.postDelayed(autoLock, 300_000L)
        }
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        vault = Vault(this)
        // Any leftovers from an interrupted PDF render are local and deleted on startup.
        cacheDir.listFiles()?.filter { it.name.startsWith("travel-pdf-") }?.forEach { it.delete() }
        setContent {
            MaterialTheme(colorScheme = darkColorScheme(primary = Teal, onPrimary = Navy, background = Navy, surface = Panel,
                onSurface = White, onBackground = White, secondary = Sand, onSurfaceVariant = Muted)) {
                Surface(Modifier.fillMaxSize(), color = Navy) { App() }
            }
        }
    }
    override fun onStop() {
        super.onStop()
        if (!authenticating) lockLocal()
    }
    private fun lockLocal() {
        epoch++
        authHandler.removeCallbacks(autoLock)
        authenticating = false
        locked = true; busy = false; connection = null; session = ""; trips = emptyList()
        current = null; offlineMeta = null; offline = false; pdf = null; pageBitmap = null; pdfName = ""; error = ""
        section = "Home"
    }
    @Suppress("DEPRECATION")
    private fun deviceUnlock() {
        if (authenticating || busy) return
        val km = getSystemService(KeyguardManager::class.java)
        if (!km.isDeviceSecure) {
            error = "Configura il PIN, la password o la sequenza di blocco del telefono."
            return
        }
        val intent = km.createConfirmDeviceCredentialIntent("NextDo Viaggi", "Inserisci il codice di blocco del telefono")
        if (intent == null) {
            error = "Verifica del codice di blocco non disponibile"
            return
        }
        authenticating = true
        error = ""
        try { authenticate.launch(intent) }
        catch (_: Exception) { authenticating = false; error = "Impossibile aprire lo sblocco Android" }
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
    private fun connect(base: String, code: String) {
        task({
            val a = TravelApi(base)
            val r = a.obj("/pair", data = JSONObject().put("code", code.trim()).put("label", "Android " + android.os.Build.MODEL.take(60)))
            val cfg = JSONObject().put("url", base.trim()).put("token", r.getString("device_token"))
            vault.write("connection", cfg.toString().toByteArray())
            cfg
        }) { connection = it }
    }
    private fun unlockServer(pin: String) {
        val cfg = connection ?: return
        task({
            val api = TravelApi(cfg.getString("url"))
            val response = api.obj("/unlock", cfg.getString("token"), JSONObject().put("pin", pin))
            val s = response.getString("session_token")
            Pair(s, api.trips(s))
        }) { (s, list) -> session = s; trips = list; offline = false }
    }
    private fun selectTrip(id: String) {
        val cfg = connection ?: return
        val s = session
        task({
            val r = TravelApi(cfg.getString("url")).obj("/trips/" + segment(id), s)
            TripPackage(r.getJSONObject("manifest"), r.optJSONObject("state") ?: JSONObject(), emptyMap())
        }) { openTrip(it, false) }
    }
    private fun openTrip(t: TripPackage, cached: Boolean) {
        current = t; offline = cached; section = "Home"
        selectedDay = t.days.firstOrNull { it.str("date") >= LocalDate.now().toString() }?.str("date")
            ?: t.days.firstOrNull()?.str("date").orEmpty()
    }
    private fun downloadTrip() {
        val cfg = connection ?: return
        val t = current ?: return
        val s = session
        task({
            val bytes = TravelApi(cfg.getString("url")).call("/trips/" + segment(t.id) + "/offline", s)
            val parsed = TripPackage.parse(bytes)
            require(parsed.id == t.id) { "Viaggio non corrispondente" }
            val meta = JSONObject().put("title", parsed.info.str("title")).put("id", parsed.id)
                .put("saved", java.time.OffsetDateTime.now().toString()).put("pdfs", parsed.docs.size)
            vault.write("offline", bytes)
            vault.write("offline_meta", meta.toString().toByteArray())
            meta
        }) { offlineMeta = it }
    }
    private fun openOffline() {
        task({ TripPackage.parse(vault.read("offline")) }) { openTrip(it, true) }
    }
    private fun forget() {
        task({ vault.clear() }) { lockLocal() }
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
        }) { (bytes, count, bmp) -> pdf = bytes; pdfName = name; page = 0; pageCount = count; pageBitmap = bmp }
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
                    val scale = minOf(1400f / p.width, 2000f / p.height, 2.0f)
                    val bmp = Bitmap.createBitmap(maxOf(1,(p.width*scale).toInt()), maxOf(1,(p.height*scale).toInt()), Bitmap.Config.ARGB_8888)
                    bmp.eraseColor(android.graphics.Color.WHITE)
                    p.render(bmp, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                    return renderer.pageCount to bmp
                }
            }
        } finally { tmp.delete() }
    }
    private fun pdfPage(index: Int) {
        val bytes = pdf ?: return
        task({ renderPage(bytes, index) }) { (count, bmp) -> pageCount = count; page = index; pageBitmap = bmp }
    }
    private fun navigate(b: JSONObject) {
        val lat = b.optDouble("lat"); val lon = b.optDouble("lon")
        val query = when {
            lat.isFinite() && lon.isFinite() && lat in -90.0..90.0 && lon in -180.0..180.0 -> "$lat,$lon"
            b.str("address").isNotBlank() -> b.str("address")
            else -> b.str("place")
        }
        val explicit = b.str("map")
        val url = when {
            query.isNotBlank() -> "https://www.google.com/maps/search/?api=1&query=" + Uri.encode(query)
            explicit.startsWith("https://") -> explicit
            else -> return
        }
        try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) } catch (_: Exception) { error = "Navigazione non disponibile" }
    }
    private fun closePdf() { pdf = null; pdfName = ""; pageBitmap = null; page = 0; pageCount = 0 }

    @Composable private fun App() {
        val t = current
        Scaffold(containerColor = Navy,
            topBar = {
                Surface(color = Navy) {
                    Row(Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal=18.dp, vertical=12.dp), verticalAlignment=Alignment.CenterVertically) {
                        Box(Modifier.size(42.dp).clip(RoundedCornerShape(14.dp)).background(Teal), contentAlignment=Alignment.Center) {
                            Icon(Icons.Default.Flight, contentDescription=null, tint=Navy)
                        }
                        Spacer(Modifier.width(10.dp))
                        Column(Modifier.weight(1f)) {
                            Text("NextDo", color=White, fontWeight=FontWeight.ExtraBold, fontSize=20.sp)
                            Text("V I A G G I", color=Teal, fontSize=10.sp, fontWeight=FontWeight.Bold)
                        }
                        if (t != null) IconButton(onClick={closePdf(); current=null; section="Home"}) { Icon(Icons.Default.ArrowBack,"Tutti i viaggi") }
                        if (!locked) IconButton(onClick={lockLocal()}) { Icon(Icons.Default.Lock,"Blocca") }
                    }
                }
            },
            bottomBar = {
                if(t != null && !locked && pdf == null) NavigationBar(containerColor=Panel) {
                    listOf("Home","Oggi","Prenota","PDF","Guide").forEach { label ->
                        val image = when(label) {
                            "Home" -> Icons.Default.Home
                            "Oggi" -> Icons.Default.CalendarToday
                            "Prenota" -> Icons.Default.ConfirmationNumber
                            "PDF" -> Icons.Default.Folder
                            else -> Icons.Default.Book
                        }
                        NavigationBarItem(selected=section==label,onClick={section=label},icon={Icon(image,label)},label={Text(label,fontSize=11.sp)},
                            colors=NavigationBarItemDefaults.colors(indicatorColor=Teal.copy(alpha=.20f),selectedIconColor=Teal,selectedTextColor=Teal,unselectedIconColor=Muted,unselectedTextColor=Muted))
                    }
                }
            }) { padding ->
            Column(Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement=Arrangement.spacedBy(14.dp)) {
                if (busy) LinearProgressIndicator(Modifier.fillMaxWidth(), color=Teal)
                if (error.isNotBlank()) Card(colors=CardDefaults.cardColors(containerColor=Color(0xFF432E37))) {
                    Row(Modifier.padding(14.dp),verticalAlignment=Alignment.CenterVertically) {
                        Text(error,Modifier.weight(1f),color=White,fontSize=13.sp)
                        TextButton(onClick={error=""}) { Text("Chiudi") }
                    }
                }
                when {
                    locked -> LockedScreen()
                    pdf != null -> PdfScreen()
                    t != null -> {
                        if (offline) Pill("OFFLINE · copia scaricata",Sand)
                        when(section) {
                            "Home" -> Home(t)
                            "Oggi" -> DayScreen(t)
                            "Prenota" -> BookingScreen(t)
                            "PDF" -> Documents(t)
                            "Guide" -> Guides(t)
                        }
                    }
                    else -> ConnectionScreen()
                }
                Spacer(Modifier.height(12.dp))
            }
        }
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
    @Composable private fun LockedScreen() {
        Box(Modifier.fillMaxWidth().height(260.dp).clip(RoundedCornerShape(28.dp)).background(Brush.linearGradient(listOf(Color(0xFF1B5271),Color(0xFF163E4B),Panel))), contentAlignment=Alignment.Center) {
            Column(horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.spacedBy(12.dp)) {
                Icon(Icons.Default.Lock,null,Modifier.size(64.dp),tint=Teal)
                Text("Il mondo, con te.",color=White,fontSize=30.sp,fontWeight=FontWeight.ExtraBold)
                Text("I tuoi viaggi. I tuoi documenti. La tua privacy.",color=Muted,fontSize=12.sp)
                Action("Sblocca archivio",!busy&&!authenticating) { deviceUnlock() }
                Text("PIN, password o sequenza del telefono",color=Muted,fontSize=12.sp)
            }
        }
        Text("Accesso con il codice di blocco del telefono, senza autenticazione biometrica nell’app. Blocco automatico all’uscita o dopo 5 minuti. Foto e voucher offline restano cifrati.",color=Muted,fontSize=13.sp)
    }
    @Composable private fun ConnectionScreen() {
        var url by remember { mutableStateOf("") }
        var code by remember { mutableStateOf("") }
        var pin by remember { mutableStateOf("") }
        var erase by remember { mutableStateOf(false) }
        val cfg = connection
        if(cfg==null) {
            TravelCard("Collega NextDo","Da NextDo Web: Area personale → Viaggi → App Android. Genera un codice monouso.") {
                OutlinedTextField(url,{url=it},label={Text("URL HTTPS di NextDo")},singleLine=true,modifier=Modifier.fillMaxWidth())
                OutlinedTextField(code,{code=it},label={Text("Codice associazione")},singleLine=true,visualTransformation=PasswordVisualTransformation(),modifier=Modifier.fillMaxWidth())
                Action("Associa dispositivo",!busy&&url.isNotBlank()&&code.isNotBlank()) { val c=code;code="";connect(url,c) }
            }
        } else if(session.isBlank()) {
            TravelCard("Viaggi sincronizzati","Inserisci il PIN della tua area personale NextDo.") {
                OutlinedTextField(pin,{pin=it.filter(Char::isDigit).take(6)},label={Text("PIN NextDo")},visualTransformation=PasswordVisualTransformation(),keyboardOptions=KeyboardOptions(keyboardType=KeyboardType.NumberPassword),singleLine=true)
                Action("Connetti",!busy&&pin.length==6) { val p=pin;pin="";unlockServer(p) }
            }
        } else {
            Text("I tuoi viaggi",fontSize=26.sp,fontWeight=FontWeight.ExtraBold,color=White)
            if(trips.isEmpty()) Text("Nessun viaggio disponibile",color=Muted)
            for (item in trips) TravelCard(item.str("title"),item.str("start")+"  —  "+item.str("end")) {
                Action("Apri viaggio") { selectTrip(item.str("id")) }
            }
            TextButton(onClick={session="";trips=emptyList()}) { Text("Riconnetti") }
        }
        offlineMeta?.let { meta ->
            TravelCard("Disponibile offline",meta.str("title")+" · "+meta.optInt("pdfs")+" PDF") {
                Pill("NESSUNA CONNESSIONE NECESSARIA")
                Text("Ultimo download: "+meta.str("saved").take(16).replace('T',' '),color=Muted,fontSize=12.sp)
                Action("Apri copia offline") { openOffline() }
            }
        }
        if(cfg!=null || offlineMeta!=null) TextButton(onClick={erase=true}) { Text("Disassocia e cancella dati locali",color=Sand) }
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
                Text(info.str("start")+" — "+info.str("end"),color=Muted,fontSize=12.sp)
            }
        }
    }
    @Composable private fun Home(t: TripPackage) {
        Hero(t)
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(10.dp)) {
            Metric(t.days.size.toString(),"Giornate",Modifier.weight(1f)){section="Oggi"}
            Metric(t.bookings.size.toString(),"Prenotazioni",Modifier.weight(1f)){section="Prenota"}
            Metric(documentMap(t).size.toString(),"PDF",Modifier.weight(1f)){section="PDF"}
        }
        val next=t.days.firstOrNull{it.str("date")==selectedDay}
        TravelCard("La prossima tappa",next?.let { listOf(it.str("date"),it.str("place"),it.str("headline")).filter{v->v.isNotBlank()}.joinToString(" · ") } ?: "Programma da definire") {
            Action("Vai all’itinerario") { section="Oggi" }
        }
        if(!offline) TravelCard("Porta il viaggio con te","Scarica itinerari, guide, foto e PDF in un unico archivio cifrato. Una sola copia offline alla volta.") {
            var replace by remember { mutableStateOf(false) }
            if(offlineMeta?.str("id")==t.id) Pill("COPIA OFFLINE PRESENTE")
            Action("Scarica / aggiorna offline") {
                if(offlineMeta!=null&&offlineMeta?.str("id")!=t.id)replace=true else downloadTrip()
            }
            if(replace) AlertDialog(onDismissRequest={replace=false},title={Text("Sostituire il viaggio offline?")},text={Text("La copia offline precedente sarà sostituita. L’archivio centrale non cambia.")},confirmButton={TextButton(onClick={replace=false;downloadTrip()}){Text("Sostituisci")}},dismissButton={TextButton(onClick={replace=false}){Text("Annulla")}})
        }
        else Text("Copia offline in sola lettura. Per aggiornare i dati torna all’elenco e connettiti a NextDo.",color=Muted,fontSize=12.sp)
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
            Text(selectedDay.ifBlank{"Nessuna giornata"},Modifier.weight(1f),color=Teal,fontSize=19.sp,fontWeight=FontWeight.Bold)
            IconButton(onClick={if(i>=0&&i<t.days.lastIndex)selectedDay=t.days[i+1].str("date")},enabled=i>=0&&i<t.days.lastIndex){Icon(Icons.Default.ArrowForward,"Giorno successivo")}
        }
        val d=t.days.firstOrNull{it.str("date")==selectedDay}?:return
        TravelCard(d.str("headline").ifBlank{d.str("place").ifBlank{"Giornata"}},d.str("description")) {
            Photo(t.manifest.optJSONObject("travel_photos")?.optJSONObject("day:"+selectedDay))
            if(d.str("place").isNotBlank())Pill(d.str("place"))
            d.arr("route_points").forEach { point -> Location(point) }
        }
        for(e in d.arr("events")) {
            val booking=t.bookings.firstOrNull{it.str("id")==e.str("bid")}
            val guide=t.guides.firstOrNull{it.str("id")==e.str("gid")}
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(10.dp)) {
                Column(Modifier.width(55.dp),horizontalAlignment=Alignment.CenterHorizontally) {
                    Text(e.str("time").ifBlank{"·"},color=Sand,fontSize=13.sp,fontWeight=FontWeight.Bold)
                    Box(Modifier.padding(top=6.dp).size(8.dp).clip(RoundedCornerShape(10.dp)).background(Teal))
                    Box(Modifier.padding(top=4.dp).width(2.dp).height(60.dp).background(Teal.copy(alpha=.3f)))
                }
                Column(Modifier.weight(1f)) {
                    TravelCard(e.str("title"),e.str("details")) {
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
            TextButton(onClick={navigate(b)}){Text("Naviga")}
        }
    }
    @Composable private fun BookingActions(b:JSONObject) {
        if(b.str("doc").isNotBlank())Action("Apri voucher PDF"){viewPdf(b.str("doc"))}
        if(b.arr("locations").isNotEmpty())b.arr("locations").forEach{Location(it)}
        else if(b.str("place").isNotBlank()||b.str("map").isNotBlank())TextButton(onClick={navigate(b)}){Icon(Icons.Default.Place,null);Spacer(Modifier.width(5.dp));Text("Apri mappa")}
    }
    @Composable private fun BookingScreen(t:TripPackage) {
        Text("Le tue prenotazioni",fontSize=26.sp,fontWeight=FontWeight.ExtraBold)
        for(b in t.bookings)TravelCard(b.str("title"),listOf(b.str("type"),b.str("date"),b.str("place")).filter{it.isNotBlank()}.joinToString(" · ")) {
            Photo(t.manifest.optJSONObject("travel_photos")?.optJSONObject("booking:"+b.str("id")))
            if(b.str("status").isNotBlank())Pill(b.str("status"))
            if(b.str("ref").isNotBlank())Text("Riferimento: "+b.str("ref"),color=Sand,fontSize=13.sp)
            if(b.str("price").isNotBlank())Text(b.str("price"),color=Teal,fontWeight=FontWeight.Bold)
            for(key in listOf("lines","fields")) {
                val a=b.optJSONArray(key)?:continue
                for(i in 0 until a.length())a.optJSONArray(i)?.let{Text(it.optString(0)+": "+it.optString(1),fontSize=13.sp,color=Muted)}
            }
            BookingActions(b)
        }
    }
    private fun documentMap(t:TripPackage):Map<String,String> {
        val docs=linkedMapOf<String,String>()
        (t.bookings+t.guides).forEach{if(it.str("doc").isNotBlank())docs[it.str("doc")]=it.str("title")}
        t.manifest.arr("documents").forEach{if(it.str("file").isNotBlank())docs[it.str("file")]=it.str("title")}
        t.manifest.arr("expenses").forEach{if(it.str("doc").isNotBlank())docs[it.str("doc")]=it.str("title")}
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
        TextButton(onClick={closePdf()}){Text("← Torna al viaggio")}
        Text(pdfName,fontSize=17.sp,fontWeight=FontWeight.Bold)
        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
            IconButton(onClick={pdfPage(page-1)},enabled=!busy&&page>0){Icon(Icons.Default.ArrowBack,"Pagina precedente")}
            Text("Pagina "+(page+1)+" / "+pageCount,Modifier.weight(1f),color=Teal)
            IconButton(onClick={pdfPage(page+1)},enabled=!busy&&page+1<pageCount){Icon(Icons.Default.ArrowForward,"Pagina successiva")}
        }
        pageBitmap?.let{Image(it.asImageBitmap(),pdfName,Modifier.fillMaxWidth(),contentScale=ContentScale.FillWidth)}
    }
}
