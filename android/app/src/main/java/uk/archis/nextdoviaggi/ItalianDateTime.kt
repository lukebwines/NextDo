package uk.archis.nextdoviaggi

import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.time.format.ResolverStyle
import java.util.Locale

/** Presentation only: no zone conversion and no modification of stored strings. */
internal object ItalianDateTime {
    private val dateFormat=DateTimeFormatter.ofPattern("dd/MM/uuuu",Locale.ITALY).withResolverStyle(ResolverStyle.STRICT)
    private val timeFormat=DateTimeFormatter.ofPattern("HH:mm",Locale.ITALY)
    private val isoDate=Regex("""\d{4}-\d{2}-\d{2}""")
    private val italianDate=Regex("""\d{2}/\d{2}/\d{4}""")
    private val clock=Regex("""(?i)(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*(AM|PM))?""")
    private val timestamp=Regex("""\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+-]\d{2}:\d{2})?""")
    fun parseDate(raw:String):LocalDate?=runCatching {
        when {
            isoDate.matches(raw.trim())->LocalDate.parse(raw.trim())
            italianDate.matches(raw.trim())->LocalDate.parse(raw.trim(),dateFormat)
            else->null
        }
    }.getOrNull()
    fun parseTime(raw:String):LocalTime?=runCatching {
        val m=clock.matchEntire(raw.trim())?:return null
        val h=m.groupValues[1].toInt()
        val marker=m.groupValues[4].uppercase(Locale.ROOT)
        val hour=if(marker.isEmpty())h else {
            require(h in 1..12)
            h%12+if(marker=="PM")12 else 0
        }
        LocalTime.of(hour,m.groupValues[2].toInt(),m.groupValues[3].ifBlank{"0"}.toInt())
    }.getOrNull()
    fun date(value:LocalDate):String=value.format(dateFormat)
    fun date(raw:String):String=parseDate(raw)?.let{date(it)}?:raw
    fun time(value:LocalTime):String=value.format(timeFormat)
    fun time(raw:String):String=parseTime(raw)?.let{time(it)}?:raw
    fun dateTime(raw:String,showOffset:Boolean=false):String {
        parseDate(raw)?.let{return date(it)}
        if(!timestamp.matches(raw))return raw
        val normalized=raw.replace(' ','T')
        val offset=runCatching{OffsetDateTime.parse(normalized)}.getOrNull()
        val local=offset?.toLocalDateTime()?:runCatching{LocalDateTime.parse(normalized)}.getOrNull()?:return raw
        return date(local.toLocalDate())+" "+time(local.toLocalTime())+
            if(showOffset&&offset!=null)" ("+offset.offset.id.replace("Z","UTC")+")" else ""
    }
    /** Only for explicit temporal text fields. Free-form content is never rewritten in storage. */
    fun temporalText(raw:String):String {
        val timestamps=Regex("""(?<!\d)\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+-]\d{2}:\d{2})?(?!\d)""")
        val dates=Regex("""(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)""")
        val times=Regex("""(?i)(?<![\d:+-])\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:AM|PM)\b)?(?!\d)""")
        // Format times before introducing display dates. Preserve offset-bearing timestamps as a whole.
        val segments=timestamps.findAll(raw).toList()
        fun plain(s:String)=dates.replace(times.replace(s){time(it.value)}){date(it.value)}
        if(segments.isEmpty())return plain(raw)
        var end=0
        return buildString {
            for(m in segments){append(plain(raw.substring(end,m.range.first)));append(dateTime(m.value,true));end=m.range.last+1}
            append(plain(raw.substring(end)))
        }
    }
    fun firstDate(raw:String):LocalDate? {
        parseDate(raw)?.let{return it}
        val candidate=Regex("""(?<!\d)(?:\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})(?!\d)""").find(raw)
        return candidate?.value?.let{parseDate(it)}
    }
    fun storedDue(original:String,day:String,clock:String):String? {
        if(day.isBlank())return null
        // Preserve exact existing seconds/precision if user only edits another field.
        if(original.take(10)==day&&original.drop(11).take(5)==clock)return original
        return day+if(clock.isBlank())"" else "T"+clock+":00"
    }
}
