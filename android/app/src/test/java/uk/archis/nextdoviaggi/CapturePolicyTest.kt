package uk.archis.nextdoviaggi
import org.junit.Assert.*
import org.junit.Test
import java.time.YearMonth
class CapturePolicyTest {
 @Test fun personalIsIndependent(){
  assertFalse(captureAllowed(true,false,35,NextDoArea.PERSONAL,true,false))
  assertFalse(captureAllowed(true,false,35,NextDoArea.TRIPS,true,false))
  assertTrue(captureAllowed(true,false,35,NextDoArea.PERSONAL,false,true))
  assertTrue(captureAllowed(true,false,35,NextDoArea.TRIPS,false,true))
  assertFalse(captureAllowed(true,false,35,NextDoArea.WORK,false,true))
  assertTrue(captureAllowed(true,false,35,NextDoArea.WORK,true,false))
 }
 @Test fun protectedStatesAlwaysProtected(){
  for(a in NextDoArea.entries){
   assertFalse(captureAllowed(false,false,35,a,true,true))
   assertFalse(captureAllowed(true,true,35,a,true,true))
   assertFalse(captureAllowed(true,false,32,a,true,true))
  }
  assertFalse(captureAllowed(true,false,35,NextDoArea.SETTINGS,true,true))
 }
 @Test fun calendarStartsMondayAndHandlesLeapYear(){
  val dates=monthCells(YearMonth.of(2028,2))
  assertEquals(42,dates.size)
  assertEquals(java.time.DayOfWeek.MONDAY,dates.first().dayOfWeek)
  assertTrue(dates.contains(java.time.LocalDate.of(2028,2,29)))
 }
}
