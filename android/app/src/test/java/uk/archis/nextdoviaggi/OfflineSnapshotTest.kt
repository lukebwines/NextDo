package uk.archis.nextdoviaggi

import org.junit.Assert.*
import org.junit.Test

class OfflineSnapshotTest {
    @Test fun equalFingerprintSkipsDownload(){
        val a="a".repeat(64)
        assertFalse(requiresOfflineDownload(a,a))
        assertTrue(requiresOfflineDownload(a,"b".repeat(64)))
        assertTrue(requiresOfflineDownload("",a))
    }
    @Test(expected=IllegalArgumentException::class)
    fun invalidRemoteFingerprintRejected(){requiresOfflineDownload("","unknown")}
    @Test fun sha256MatchesKnownValue(){
        assertEquals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",sha256("abc".toByteArray()))
    }
}
