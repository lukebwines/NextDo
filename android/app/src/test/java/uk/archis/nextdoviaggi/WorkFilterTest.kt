package uk.archis.nextdoviaggi

import org.junit.Assert.*
import org.junit.Test

class WorkFilterTest {
    private fun item(id:Long,kind:String="task",status:String="todo",day:String="",priority:String="normal",overdue:Boolean=false)=
        WorkItem(id,"Synthetic",kind,priority,status,day,"",overdue,"revision",false)

    @Test fun defaultIncludesUndatedAndFutureActivities() {
        val all=listOf(item(1),item(2,day="2027-02-01"),item(3,kind="appointment",status="review",day="2026-12-02"))
        assertEquals(all.toSet(),all.filter{workMatches(it,"all")}.toSet())
        assertEquals(listOf(1L,2L),all.filter{workMatches(it,"todo")}.map{it.id})
        assertEquals(listOf(1L),all.filter{workMatches(it,"undated")}.map{it.id})
        assertEquals(listOf(3L),all.filter{workMatches(it,"appointments")}.map{it.id})
        assertEquals(listOf(3L),all.filter{workMatches(it,"review")}.map{it.id})
        assertEquals(listOf(1L,2L),all.filter{workMatches(it,"tasks")}.map{it.id})
    }
    @Test fun dashboardPrioritizesWithoutDroppingOpenItems(){
        val all=listOf(item(1),item(2,day="2027-02-01"),item(3,status="review"),item(4,priority="high"),item(5,overdue=true,day="2026-11-01"))
        assertEquals(listOf(5L,4L,3L,2L,1L),orderedWork(all).map{it.id})
        assertEquals(listOf(4L),all.filter{workMatches(it,"urgent")}.map{it.id})
    }
}
