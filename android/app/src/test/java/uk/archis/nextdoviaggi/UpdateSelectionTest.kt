package uk.archis.nextdoviaggi

import org.junit.Assert.*
import org.junit.Test

class UpdateSelectionTest {
    private fun release(version:String,code:Long)=TravelUpdate(version,code,"a".repeat(64),"https://example.invalid/file.apk","")
    @Test fun oldFirstDoesNotHideNewRelease() {
        val newest=release("0.1.11-test",12)
        assertEquals(newest,newestUpdate(11,sequenceOf(release("0.1.6-test",7),release("0.1.5-test",6),release("0.1.4-test",5),newest,release("0.1.10-test",11))))
    }
    @Test fun selectsHighestCodeRegardlessOfOrder() {
        val newest=release("0.1.12-test",13)
        assertEquals(newest,newestUpdate(7,sequenceOf(release("0.1.10-test",11),newest,release("0.1.11-test",12))))
    }
    @Test fun currentAndOlderAreNotUpdates() {
        assertNull(newestUpdate(13,sequenceOf(release("0.1.6-test",7),release("0.1.12-test",13))))
        assertNull(newestUpdate(13,emptySequence()))
    }
    @Test(expected=IllegalStateException::class) fun incompleteListingIsNotNoUpdate() {
        newestUpdate(7,sequence {
            yield(release("0.1.6-test",7))
            error("Network unavailable")
        })
    }
}
