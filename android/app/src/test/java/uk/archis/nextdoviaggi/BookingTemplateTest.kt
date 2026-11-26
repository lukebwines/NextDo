package uk.archis.nextdoviaggi

import org.junit.Assert.*
import org.junit.Test

class BookingTemplateTest {
    @Test fun explicitTypeTakesPrecedence(){
        assertEquals("custom-test",inferBookingKind("custom-test","Hotel",emptyList()))
        assertEquals("insurance",inferBookingKind("","Polizza viaggio",emptyList()))
        assertEquals("parking",inferBookingKind("","Airport parking",emptyList()))
    }
    @Test fun matchesCustomLabel(){
        val t=BookingTemplate("custom-test","Transfer speciale","car",listOf("Codice"),emptyList())
        assertEquals(t.id,inferBookingKind("","transfer SPECIALE",listOf(t)))
    }
    @Test fun suggestionsKeepExistingAndAvoidDuplicates(){
        assertEquals(listOf("Terminal"),missingTemplateFields(listOf(" Codice ","Campo storico"),listOf("codice","Terminal","terminal")))
    }
    @Test fun unusedSuggestionsAreNotPersisted(){
        val original=BookingField("Legacy","")
        val entered=BookingField("Terminal","A",false,true)
        val unused=BookingField("Deposito","",false,true)
        val custom=BookingField("Campo libero","",false,false)
        assertEquals(listOf(original,entered,custom),retainedBookingFields(listOf(original,entered,unused,custom)))
    }
}
