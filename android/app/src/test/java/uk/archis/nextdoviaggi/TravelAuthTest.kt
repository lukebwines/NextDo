package uk.archis.nextdoviaggi
import org.junit.Assert.assertEquals
import org.junit.Test
class TravelAuthTest {
    @Test fun onlyExplicitServerChallengeRequiresPin(){
        assertEquals(TravelAuthState.PIN_REQUIRED,resumeFailure(401,"Verifica PIN NextDo necessaria"))
        assertEquals(TravelAuthState.REPAIR_REQUIRED,resumeFailure(401,"Sessione scaduta o dispositivo revocato"))
        assertEquals(TravelAuthState.RETRY,resumeFailure(503,null))
        assertEquals(TravelAuthState.RETRY,resumeFailure(401,null))
    }
}
