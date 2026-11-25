package uk.archis.nextdoviaggi

import org.junit.Assert.*
import org.junit.Test

class PdfViewerTest {
    @Test fun zoomAndPanAreBounded(){
        assertEquals(1f,pdfZoom(0.2f),0f)
        assertEquals(5f,pdfZoom(9f),0f)
        assertEquals(0f,pdfPan(100f,100f,200f,1f),0f)
        assertEquals(50f,pdfPan(100f,100f,200f,3f),0f)
        assertEquals(-50f,pdfPan(-100f,100f,200f,3f),0f)
    }
    @Test fun exportNameIsSafe(){
        assertEquals("policy.pdf",PdfExport.safeName("policy.pdf"))
        assertEquals("documento.pdf",PdfExport.safeName("..."))
        assertFalse(PdfExport.safeName("../unsafe\\path.pdf").contains("/"))
        assertFalse(PdfExport.safeName("../unsafe\\path.pdf").contains("\\"))
    }
}
