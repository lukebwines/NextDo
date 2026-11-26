package uk.archis.nextdoviaggi

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.AtomicFile
import org.json.JSONObject
import org.json.JSONArray
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.net.URLEncoder
import java.security.KeyStore
import java.util.zip.ZipInputStream
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

private const val MAX = 32 * 1024 * 1024
private const val EXPANDED = 120 * 1024 * 1024
fun JSONObject.arr(key: String): List<JSONObject> {
    val a = optJSONArray(key) ?: return emptyList()
    return (0 until a.length()).mapNotNull { a.optJSONObject(it) }
}
fun JSONObject.str(key: String): String = if (isNull(key)) "" else optString(key, "")
fun segment(s: String) = URLEncoder.encode(s, "UTF-8").replace("+", "%20")
fun readLimited(input: InputStream, limit: Int): ByteArray {
    val output = ByteArrayOutputStream()
    val buffer = ByteArray(8192)
    var total = 0
    while (true) {
        val n = input.read(buffer)
        if (n < 0) break
        total += n
        require(total <= limit) { "Archivio troppo grande" }
        output.write(buffer, 0, n)
    }
    return output.toByteArray()
}

internal class TravelHttpException(val status:Int,val detail:String?):IllegalStateException("HTTP "+status+if(!detail.isNullOrBlank())" · "+detail else "")
internal enum class TravelAuthState { PIN_REQUIRED, RETRY, REPAIR_REQUIRED, CONNECTED }
internal fun resumeFailure(status:Int,detail:String?):TravelAuthState = when {
    status==401 && detail=="Verifica PIN NextDo necessaria" -> TravelAuthState.PIN_REQUIRED
    status==401 && detail in setOf("Sessione scaduta o dispositivo revocato","Account non disponibile","Credenziale non valida") -> TravelAuthState.REPAIR_REQUIRED
    else -> TravelAuthState.RETRY
}
class TravelApi(base: String) {
    private val root: String
    init {
        val u = URI(base.trim())
        require(u.scheme == "https" && u.host != null && u.userInfo == null && u.query == null && u.fragment == null) {
            "Inserisci un URL HTTPS diretto di NextDo"
        }
        root = u.toASCIIString().trimEnd('/') + "/api/mobile/v1"
    }
    fun call(path: String, token: String? = null, data: JSONObject? = null, limit: Int = MAX, zip: ByteArray? = null, responseHeaders: ((HttpURLConnection)->Unit)? = null): ByteArray {
        val c = URL(root + path).openConnection() as HttpURLConnection
        try {
            c.instanceFollowRedirects = false
            c.connectTimeout = 15000
            c.readTimeout = 60000
            c.useCaches = false
            c.setRequestProperty("Accept", "*/*")
            if (token != null) c.setRequestProperty("Authorization", "Bearer " + token)
            if (zip != null) {
                require(zip.size <= MAX) { "Archivio oltre 32 MB" }
                c.requestMethod = "POST"
                c.doOutput = true
                c.setFixedLengthStreamingMode(zip.size)
                c.setRequestProperty("Content-Type", "application/zip")
                c.outputStream.use { it.write(zip) }
            } else if (data != null) {
                c.requestMethod = "POST"
                c.doOutput = true
                c.setRequestProperty("Content-Type", "application/json")
                c.outputStream.use { it.write(data.toString().toByteArray(Charsets.UTF_8)) }
            }
            val status = c.responseCode
            if (status !in 200..299) {
                val detail = try {
                    c.errorStream?.use { JSONObject(String(readLimited(it, 4096), Charsets.UTF_8)).optString("detail") }
                } catch (_: Exception) { null }
                throw TravelHttpException(status,detail)
            }
            responseHeaders?.invoke(c)
            return c.inputStream.use { readLimited(it, limit) }
        } finally { c.disconnect() }
    }
    fun obj(path: String, token: String? = null, data: JSONObject? = null) =
        JSONObject(String(call(path, token, data), Charsets.UTF_8))
    fun importZip(token: String, raw: ByteArray) = JSONObject(String(call("/trips/import", token, zip=raw), Charsets.UTF_8))
    fun trips(token: String): List<JSONObject> {
        val a = JSONArray(String(call("/trips", token), Charsets.UTF_8))
        return (0 until a.length()).map { a.getJSONObject(it) }
    }
}
data class TripPackage(val manifest: JSONObject, val state: JSONObject, val docs: Map<String,ByteArray>, val revision: Int = -1, val timeline: JSONObject? = null) {
    val info get() = manifest.getJSONObject("trip")
    val id get() = info.getString("id")
    val bookings get() = manifest.arr("bookings")
    val days get() = manifest.arr("days")
    val guides get() = manifest.arr("guides")
    companion object {
        fun parse(raw: ByteArray): TripPackage {
            val files = linkedMapOf<String,ByteArray>()
            var total = 0
            ZipInputStream(ByteArrayInputStream(raw)).use { zip ->
                var entries = 0
                while (true) {
                    val e = zip.nextEntry ?: break
                    require(++entries <= 180) { "Archivio non valido" }
                    if (e.isDirectory) continue
                    val name = e.name
                    require(name == "manifest.json" || name == "notes.json" || name == "timeline.json" ||
                        (name.startsWith("documenti/") && name.substring(10).matches(Regex("[^/\\\\]{1,128}\\.pdf", RegexOption.IGNORE_CASE)))) { "Percorso non valido" }
                    require(!files.containsKey(name)) { "File duplicato" }
                    val bytes = readLimited(zip, minOf(MAX, EXPANDED - total))
                    total += bytes.size
                    files[name] = bytes
                    zip.closeEntry()
                }
            }
            val manifest = JSONObject(String(files.remove("manifest.json") ?: error("Manifest mancante"), Charsets.UTF_8))
            require(manifest.optInt("format_version") == 1)
            val state = JSONObject(String(files.remove("notes.json") ?: "{}".toByteArray(), Charsets.UTF_8))
            val timeline=files.remove("timeline.json")?.let { JSONObject(String(it,Charsets.UTF_8)) }
            val docs = files.mapKeys { it.key.removePrefix("documenti/") }
            require(docs.values.all { it.size >= 5 && String(it,0,5,Charsets.US_ASCII) == "%PDF-" })
            return TripPackage(manifest, state, docs, timeline=timeline)
        }
    }
}
class Vault(private val context: Context, private val background:Boolean=false) {
    private val alias = if(background) "nextdo_alerts_v1" else "nextdo_travel_v1"
    private val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
    private fun key(): SecretKey {
        (store.getKey(alias, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setUserAuthenticationRequired(!background)
                .apply { if(!background)setUserAuthenticationParameters(300, KeyProperties.AUTH_DEVICE_CREDENTIAL or KeyProperties.AUTH_BIOMETRIC_STRONG) }
                .build())
            generateKey()
        }
    }
    private fun file(name: String) = File(context.filesDir, (if(background)"alerts_" else "travel_") + name + ".enc")
    fun exists(name: String) = file(name).exists()
    fun write(name: String, raw: ByteArray) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        cipher.updateAAD(name.toByteArray())
        val encrypted = cipher.doFinal(raw)
        val atomic = AtomicFile(file(name))
        val out = atomic.startWrite()
        try {
            out.write(cipher.iv.size)
            out.write(cipher.iv)
            out.write(encrypted)
            atomic.finishWrite(out)
        } catch (e: Exception) { atomic.failWrite(out); throw e }
    }
    fun read(name: String): ByteArray {
        val raw = AtomicFile(file(name)).readFully()
        require(raw.isNotEmpty() && raw[0].toInt() == 12 && raw.size > 29)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, raw.copyOfRange(1,13)))
        cipher.updateAAD(name.toByteArray())
        return cipher.doFinal(raw,13,raw.size-13)
    }
    fun remove(name: String) = AtomicFile(file(name)).delete()
    fun clear() {
        remove("connection"); remove("offline"); remove("offline_meta"); remove("offline_snapshot")
        if (!exists("work_connection") && store.containsAlias(alias)) store.deleteEntry(alias)
    }
}
