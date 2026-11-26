package uk.archis.nextdoviaggi

import org.json.JSONObject
import java.nio.ByteBuffer
import java.security.MessageDigest
import java.time.OffsetDateTime

internal const val OFFLINE_FILE = "offline_snapshot"
private const val MAX_ZIP = 32 * 1024 * 1024
private const val MAX_META = 16384

internal fun sha256(raw:ByteArray):String = MessageDigest.getInstance("SHA-256")
    .digest(raw).joinToString(""){"%02x".format(it.toInt() and 255)}
internal fun isSnapshot(value:String):Boolean=value.matches(Regex("[a-f0-9]{64}"))
internal fun requiresOfflineDownload(local:String,remote:String):Boolean {
    require(isSnapshot(remote)){"Versione server non valida"}
    return !isSnapshot(local)||local!=remote
}
internal data class OfflineSnapshot(val meta:JSONObject,val raw:ByteArray) {
    fun encode():ByteArray {
        val header=meta.toString().toByteArray(Charsets.UTF_8)
        require(header.size in 1..MAX_META && raw.size in 1..MAX_ZIP)
        return ByteBuffer.allocate(4+header.size+raw.size).putInt(header.size).put(header).put(raw).array()
    }
    fun trip():TripPackage {
        val t=TripPackage.parse(raw)
        require(t.id==meta.str("id")){"Copia offline non corrispondente"}
        return t.copy(revision=meta.optInt("revision",-1))
    }
    companion object {
        fun decode(bytes:ByteArray,owner:String):OfflineSnapshot {
            require(bytes.size in 5..(MAX_ZIP+MAX_META+4)){"Copia offline non valida"}
            val buffer=ByteBuffer.wrap(bytes);val size=buffer.int
            require(size in 1..MAX_META && size<buffer.remaining() && buffer.remaining()-size<=MAX_ZIP){"Copia offline non valida"}
            val header=ByteArray(size);buffer.get(header)
            val meta=JSONObject(String(header,Charsets.UTF_8))
            require(meta.str("owner")==owner && meta.str("id").isNotBlank()){"Copia offline di un’altra associazione"}
            val zip=ByteArray(buffer.remaining());buffer.get(zip)
            require(isSnapshot(meta.str("archive_sha256"))&&sha256(zip)==meta.str("archive_sha256")){"Copia offline non integra"}
            return OfflineSnapshot(meta,zip)
        }
        fun download(api:TravelApi,token:String,id:String,owner:String,requireVersion:Boolean):OfflineSnapshot {
            var revision=-1;var stamp="";var digest=""
            val raw=api.call("/trips/"+segment(id)+"/offline?include_timeline=true&include_catalog=true",token,responseHeaders={c->
                revision=c.getHeaderField("X-NextDo-Revision")?.toIntOrNull()?:-1
                stamp=c.getHeaderField("X-NextDo-Snapshot").orEmpty()
                digest=c.getHeaderField("X-NextDo-Archive-SHA256").orEmpty()
            })
            val hash=sha256(raw)
            if(requireVersion||stamp.isNotBlank()||digest.isNotBlank()){
                require(revision>=0&&isSnapshot(stamp)&&isSnapshot(digest)&&digest==hash){"Archivio incompleto o versione non valida"}
            }
            val parsed=TripPackage.parse(raw)
            require(parsed.id==id){"Viaggio non corrispondente"}
            val refs=mutableSetOf<String>()
            fun ref(name:String){if(name.isNotBlank())refs.add(name)}
            for(key in listOf("bookings","guides","expenses"))for(item in parsed.manifest.arr(key)){
                ref(item.str("doc"))
                for(a in item.arr("attachments"))ref(a.str("file"))
            }
            for(item in parsed.manifest.arr("documents"))ref(item.str("file"))
            require(refs==parsed.docs.keys){"PDF mancanti o non dichiarati"}
            val meta=JSONObject().put("owner",owner).put("id",id).put("title",parsed.info.str("title"))
                .put("saved",OffsetDateTime.now().toString()).put("pdfs",parsed.docs.size)
                .put("revision",revision).put("snapshot",stamp).put("archive_sha256",hash)
            return OfflineSnapshot(meta,raw)
        }
    }
}
