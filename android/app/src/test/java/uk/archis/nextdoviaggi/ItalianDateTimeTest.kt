package uk.archis.nextdoviaggi

import org.junit.Assert.*
import org.junit.Test
import java.time.LocalDate
import java.time.LocalTime

class ItalianDateTimeTest {
    @Test fun datesAreItalianAndStrict(){
        assertEquals("26/11/2026",ItalianDateTime.date("2026-11-26"))
        assertEquals(LocalDate.of(2028,2,29),ItalianDateTime.parseDate("29/02/2028"))
        assertNull(ItalianDateTime.parseDate("29/02/2026"))
        assertNull(ItalianDateTime.parseDate("11/26/2026"))
        assertEquals("2026-11-26",ItalianDateTime.parseDate("26/11/2026").toString())
    }
    @Test fun timesAre24Hour(){
        assertEquals("08:30",ItalianDateTime.time("8:30"))
        assertEquals("21:00",ItalianDateTime.time("9:00 PM"))
        assertEquals("00:15",ItalianDateTime.time("12:15 AM"))
        assertEquals("12:15",ItalianDateTime.time("12:15 PM"))
        assertNull(ItalianDateTime.parseTime("25:00"))
        assertNull(ItalianDateTime.parseTime("13:00 PM"))
    }
    @Test fun localTimesAreNeverConverted(){
        assertEquals("04/12/2026 20:05 (-08:00)",ItalianDateTime.dateTime("2026-12-04T20:05:45-08:00",true))
        assertEquals("05/12/2026 08:15",ItalianDateTime.dateTime("2026-12-05T08:15:00Z"))
        assertEquals("04/12/2026",ItalianDateTime.dateTime("2026-12-04"))
        assertEquals("04/12/2026 — 13/12/2026",ItalianDateTime.temporalText("2026-12-04 — 2026-12-13"))
        assertEquals("09:00 – 21:00",ItalianDateTime.temporalText("9:00 AM – 9:00 PM"))
        assertEquals("orario da definire",ItalianDateTime.temporalText("orario da definire"))
        assertEquals("04/12/2026 20:05 (-08:00)",ItalianDateTime.temporalText("2026-12-04T20:05:45-08:00"))
    }
    @Test fun optionalValuesAndPrecisionStayIntact(){
        assertNull(ItalianDateTime.storedDue("2026-11-26T08:30:00","",""))
        assertEquals("2026-11-26",ItalianDateTime.storedDue("","2026-11-26",""))
        assertEquals("2026-11-26T08:30:00",ItalianDateTime.storedDue("","2026-11-26","08:30"))
        assertEquals("2026-11-26T08:30:27",ItalianDateTime.storedDue("2026-11-26T08:30:27","2026-11-26","08:30"))
        assertEquals("2026-11-26",ItalianDateTime.storedDue("2026-11-26T08:30:27","2026-11-26",""))
    }
}
