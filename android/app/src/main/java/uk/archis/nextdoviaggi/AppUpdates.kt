package uk.archis.nextdoviaggi

import android.content.Context
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import java.io.File
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import org.json.JSONArray
import org.json.JSONObject

data class TravelUpdate(val version: String, val code: Long, val sha256: String, val apkUrl: String, val notes: String)

internal fun newestUpdate(current: Long, candidates: Sequence<TravelUpdate>): TravelUpdate? =
    candidates.filter { it.code > current }.maxByOrNull { it.code }

object AppUpdates {
    private const val REPO = "lukebwines/NextDo"
    private const val LIMIT = 64 * 1024 * 1024
    private val hosts = setOf("api.github.com", "github.com", "release-assets.githubusercontent.com",
        "objects.githubusercontent.com", "github-releases.githubusercontent.com")
    private val tagPattern = Regex("android-v[0-9]+\\.[0-9]+\\.[0-9]+(?:-test)?")
    private val hashPattern = Regex("[a-f0-9]{64}")

    private fun <T> get(raw: String, limit: Int, consume: (InputStream) -> T): T {
        var url = URL(raw)
        repeat(6) {
            require(url.protocol == "https" && url.host in hosts && url.userInfo == null &&
                (url.port == -1 || url.port == 443)) { "Indirizzo aggiornamento non valido" }
            val c = url.openConnection() as HttpURLConnection
            try {
                c.instanceFollowRedirects = false
                c.connectTimeout = 12000
                c.readTimeout = 30000
                c.useCaches = false
                c.setRequestProperty("Cache-Control", "no-cache")
                c.setRequestProperty("User-Agent", "NextDo-Viaggi-Android")
                val code = c.responseCode
                if (code in 300..399) {
                    val location = c.getHeaderField("Location") ?: error("Redirect non valido")
                    url = URL(url, location)
                } else {
                    require(code == 200) { "GitHub non disponibile (HTTP " + code + ")" }
                    require(c.contentLengthLong <= limit.toLong()) { "Download troppo grande" }
                    return c.inputStream.use(consume)
                }
            } finally { c.disconnect() }
        }
        error("Troppi reindirizzamenti")
    }
    private fun text(url: String, limit: Int): String =
        get(url, limit) { String(readLimited(it, limit), Charsets.UTF_8) }

    @Suppress("DEPRECATION")
    fun check(context: Context): TravelUpdate? {
        val current = context.packageManager.getPackageInfo(context.packageName, 0).longVersionCode
        // GitHub's listing is not guaranteed to be ordered by Android versionCode.
        // Read all pages before selecting, even when an older release appears first.
        val candidates = sequence {
            var page = 1
            while (true) {
                val releases = JSONArray(text("https://api.github.com/repos/$REPO/releases?per_page=100&page=$page", 4 * 1024 * 1024))
                for (i in 0 until releases.length()) {
                    val r = releases.getJSONObject(i)
                    val tag = r.optString("tag_name")
                    if (r.optBoolean("draft") || !tagPattern.matches(tag)) continue
                    val assets = r.optJSONArray("assets") ?: continue
                    val names = (0 until assets.length()).map { assets.getJSONObject(it).optString("name") }
                    if (!names.containsAll(listOf("nextdo-viaggi.apk", "nextdo-viaggi.json"))) continue
                    val base = "https://github.com/$REPO/releases/download/$tag/"
                    val meta = JSONObject(text(base + "nextdo-viaggi.json", 8192))
                    val version = meta.getString("versionName")
                    val code = meta.getLong("versionCode")
                    val sha = meta.getString("sha256")
                    require("android-v$version" == tag && code > 0 && hashPattern.matches(sha) &&
                        meta.getString("packageName") == context.packageName) { "Metadati aggiornamento non validi" }
                    yield(TravelUpdate(version, code, sha, base + "nextdo-viaggi.apk",
                        r.optString("body").take(1600)))
                }
                if (releases.length() < 100) break
                check(page < 10) { "Elenco aggiornamenti incompleto" }
                page++
            }
        }
        return newestUpdate(current, candidates)
    }

    private fun ByteArray.hex() = joinToString("") { "%02x".format(it.toInt() and 255) }
    @Suppress("DEPRECATION")
    private fun signers(info: PackageInfo): Set<String> {
        val signatures = info.signingInfo?.apkContentsSigners ?: error("Firma APK mancante")
        require(signatures.isNotEmpty()) { "Firma APK mancante" }
        return signatures.map { MessageDigest.getInstance("SHA-256").digest(it.toByteArray()).hex() }.toSet()
    }

    @Suppress("DEPRECATION")
    fun download(context: Context, update: TravelUpdate): File {
        val dir = File(context.cacheDir, "updates").apply { mkdirs() }
        val target = File(dir, "nextdo-viaggi.apk")
        val tmp = File(dir, "nextdo-viaggi.part")
        tmp.delete(); target.delete()
        try {
            val digest = MessageDigest.getInstance("SHA-256")
            get(update.apkUrl, LIMIT) { input ->
                tmp.outputStream().use { output ->
                    val buffer = ByteArray(16384)
                    var total = 0
                    while (true) {
                        val n = input.read(buffer)
                        if (n < 0) break
                        total += n
                        require(total <= LIMIT) { "APK troppo grande" }
                        digest.update(buffer, 0, n); output.write(buffer, 0, n)
                    }
                }
            }
            require(digest.digest().hex() == update.sha256) { "Integrità APK non verificata" }
            require(tmp.renameTo(target)) { "Impossibile salvare APK" }
            val pm = context.packageManager
            val installed = pm.getPackageInfo(context.packageName, PackageManager.GET_SIGNING_CERTIFICATES)
            val candidate = pm.getPackageArchiveInfo(target.absolutePath, PackageManager.GET_SIGNING_CERTIFICATES)
                ?: error("APK non valido")
            require(candidate.packageName == context.packageName && candidate.longVersionCode == update.code &&
                candidate.longVersionCode > installed.longVersionCode) { "Versione o applicazione non corrispondente" }
            require(signers(candidate) == signers(installed)) {
                "Firma differente dalla versione installata. Non disinstallare prima di verificare la release."
            }
            return target
        } catch (e: Exception) {
            tmp.delete(); target.delete(); throw e
        }
    }
}
