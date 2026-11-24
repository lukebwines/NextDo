package uk.archis.nextdoviaggi

import android.util.JsonReader
import android.util.JsonToken
import org.json.JSONObject
import org.json.JSONArray
import java.io.InputStream
import java.io.InputStreamReader
import java.time.LocalDate
import java.time.OffsetDateTime

/** Only whitelisted, date-filtered fields leave the phone. No GPS or account API. */
object TimelineImport {
    private fun timestamp(v:String):OffsetDateTime? = try { OffsetDateTime.parse(v) } catch(_:Exception){null}
    private fun point(v:String):JSONObject? {
        val m=Regex("""^\s*(?:geo:)?(-?\d+(?:\.\d+)?)\s*°?\s*,\s*(-?\d+(?:\.\d+)?)\s*°?\s*$""").matchEntire(v) ?: return null
        val a=m.groupValues[1].toDoubleOrNull() ?: return null
        val b=m.groupValues[2].toDoubleOrNull() ?: return null
        if(a !in -90.0..90.0 || b !in -180.0..180.0)return null
        return JSONObject().put("lat",a).put("lon",b)
    }
    private fun readValue(r:JsonReader,depth:Int=0):Any {
        require(depth<40){"Formato JSON non valido"}
        return when(r.peek()){
            JsonToken.BEGIN_OBJECT -> JSONObject().apply {
                r.beginObject();while(r.hasNext()){val k=r.nextName();put(k,readValue(r,depth+1))};r.endObject()
            }
            JsonToken.BEGIN_ARRAY -> JSONArray().apply {
                r.beginArray();while(r.hasNext())put(readValue(r,depth+1));r.endArray()
            }
            JsonToken.STRING -> r.nextString()
            JsonToken.NUMBER -> r.nextString().toDoubleOrNull()?.takeIf{it.isFinite()} ?: JSONObject.NULL
            JsonToken.BOOLEAN -> r.nextBoolean()
            JsonToken.NULL -> {r.nextNull();JSONObject.NULL}
            else -> error("Formato JSON non valido")
        }
    }
    fun parse(input:InputStream,from:String,to:String):JSONObject {
        val lo=LocalDate.parse(from);val hi=LocalDate.parse(to)
        require(!hi.isBefore(lo)&&!hi.isAfter(lo.plusDays(366))){"Intervallo non valido"}
        val visits=JSONArray();val activities=JSONArray();val paths=JSONArray();val seen=HashSet<String>()
        var count=0
        fun within(t:OffsetDateTime)=!t.toLocalDate().isBefore(lo)&&!t.toLocalDate().isAfter(hi)
        fun add(kind:String,a:JSONArray,v:Any,n:Int=1){
            if(seen.add(kind+v.toString())){
                count+=n;require(count<=30000){"Troppi dati: seleziona un periodo più breve"};a.put(v)
            }
        }
        fun normalized(t:OffsetDateTime):String=t.format(java.time.format.DateTimeFormatter.ISO_OFFSET_DATE_TIME)
        fun handle(s:JSONObject){
            val start=timestamp(s.str("startTime"))?:return
            val end=timestamp(s.str("endTime"))?:return
            if(end.isBefore(start))return
            val route=s.optJSONArray("timelinePath")
            if(route!=null){
                var path=JSONArray();var previous:OffsetDateTime?=null
                fun flush(){if(path.length()>0)add("p",paths,path,path.length());path=JSONArray();previous=null}
                for(i in 0 until route.length()){
                    val p=route.optJSONObject(i)
                    val offset=p?.str("durationMinutesOffsetFromStartTime")?.toDoubleOrNull()
                    val t=p?.let{timestamp(it.str("time"))} ?: offset?.takeIf{it.isFinite()&&it>=0&&it<=527040}?.let{start.plusSeconds((it*60).toLong())}
                    val c=p?.let{point(it.str("point"))}
                    if(t==null||c==null||!within(t)||t.isBefore(start)||t.isAfter(end)){flush();continue}
                    val last=previous
                    if(last!=null&&!t.isAfter(last))flush()
                    path.put(c.put("time",normalized(t)));previous=t
                }
                flush()
            }
            if(!within(start)||!within(end))return
            fun times()=JSONObject().put("startTime",normalized(start)).put("endTime",normalized(end))
            val visit=s.optJSONObject("visit")?.optJSONObject("topCandidate")
            visit?.let{point(it.optJSONObject("placeLocation")?.str("latLng").orEmpty()) ?: point(it.str("placeLocation"))}
                ?.let{add("v",visits,times().put("location",it))}
            s.optJSONObject("activity")?.let{a->
                fun endpoint(key:String)=point(a.optJSONObject(key)?.str("latLng").orEmpty()) ?: point(a.str(key))
                val first=endpoint("start");val last=endpoint("end")
                if(first!=null&&last!=null){
                    val d=a.optDouble("distanceMeters",a.optDouble("distance",Double.NaN)).takeIf{it.isFinite()&&it in 0.0..50000000.0}
                    val m=a.optJSONObject("topCandidate")?.str("type")?.uppercase()?.takeIf{it.matches(Regex("[A-Z_]{1,60}"))}
                    add("a",activities,times().put("first",first).put("last",last).put("distanceMeters",d?:JSONObject.NULL).put("mode",m?:JSONObject.NULL))
                }
            }
        }
        // Limit input size; parse one semantic segment at a time.
        val bytes=readLimited(input,32*1024*1024)
        JsonReader(InputStreamReader(bytes.inputStream(),Charsets.UTF_8)).use{r->
            fun array(){r.beginArray();while(r.hasNext()){val s=readValue(r);if(s is JSONObject)handle(s)};r.endArray()}
            when(r.peek()){
                JsonToken.BEGIN_ARRAY -> array()
                JsonToken.BEGIN_OBJECT -> {
                    var found=false;r.beginObject()
                    while(r.hasNext()){if(r.nextName()=="semanticSegments"){require(!found);found=true;array()}else r.skipValue()}
                    r.endObject();require(found){"Formato Cronologia Google non supportato"}
                }
                else -> error("Formato Cronologia Google non supportato")
            }
            require(r.peek()==JsonToken.END_DOCUMENT){"Formato JSON non valido"}
        }
        require(count>0){"Nessuno spostamento compatibile nell’intervallo"}
        return JSONObject().put("from",from).put("to",to).put("visits",visits).put("activities",activities).put("paths",paths)
    }
}
