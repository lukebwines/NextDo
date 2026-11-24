package uk.archis.nextdoviaggi

import android.graphics.Bitmap
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import java.time.OffsetDateTime
import java.time.Duration
import kotlin.math.*

private data class DiaryPoint(val lat:Double,val lon:Double)
private fun point(p:JSONObject?):DiaryPoint? {
    if(p==null)return null
    val lat=p.optDouble("lat");val lon=p.optDouble("lon")
    return if(lat.isFinite()&&lon.isFinite()&&lat in -90.0..90.0&&lon in -180.0..180.0) DiaryPoint(lat,lon) else null
}
private fun merc(p:DiaryPoint):Pair<Double,Double> {
    val lat=p.lat.coerceIn(-85.05112878,85.05112878)*PI/180
    return (p.lon+180)/360 to (1-asinh(tan(lat))/PI)/2
}
private data class DiaryFrame(val z:Int,val x:Int,val y:Int,val anchor:Double) {
    val n get()=1 shl z
    val tileX get()=((x%n)+n)%n
    fun project(p:DiaryPoint):Offset {
        val (a,b)=merc(p);val u=anchor+((a-anchor+1.5)%1)-.5
        return Offset(((u*n-x+1)*256).toFloat(),((b*n-y+1)*256).toFloat())
    }
}
private fun frame(points:List<DiaryPoint>):DiaryFrame? {
    if(points.isEmpty())return null
    val anchor=merc(points.first()).first
    val coords=points.map { val (x,y)=merc(it); (anchor+((x-anchor+1.5)%1)-.5) to y }
    val minX=coords.minOf{it.first};val maxX=coords.maxOf{it.first}
    val minY=coords.minOf{it.second};val maxY=coords.maxOf{it.second}
    val z=floor(log2(1/maxOf(1e-9,maxX-minX,maxY-minY))).toInt().coerceIn(0,18)
    val n=1 shl z
    return DiaryFrame(z,floor((minX+maxX)/2*n).toInt(),floor((minY+maxY)/2*n).toInt().coerceIn(0,n-1),anchor)
}
@Composable
fun DiaryViewer(t:TripPackage,data:JSONObject?,loadMap:((Int,Int,Int,(Bitmap)->Unit)->Unit)?,busy:Boolean) {
    var day by remember(t.id){mutableStateOf("")}
    val dates=(t.days.map{it.str("date")}+(data?.arr("visits")?:emptyList()).map{it.str("startTime").take(10)}+
        (data?.arr("activities")?:emptyList()).map{it.str("startTime").take(10)}).filter{it.isNotBlank()}.distinct().sorted()
    val match:(String)->Boolean={day.isBlank()||it.take(10)==day}
    val visits=(data?.arr("visits")?:emptyList()).filter{match(it.str("startTime"))}
    val acts=(data?.arr("activities")?:emptyList()).filter{match(it.str("startTime"))}
    val plans=t.days.filter{day.isBlank()||it.str("date")==day}.map{it.arr("route_points").mapNotNull{p->point(p)}}.filter{it.isNotEmpty()}
    val paths=mutableListOf<List<DiaryPoint>>()
    data?.optJSONArray("paths")?.let{a->for(i in 0 until a.length()){
        val group=a.optJSONArray(i)?:continue;var current=mutableListOf<DiaryPoint>()
        for(j in 0 until group.length()){
            val p=group.optJSONObject(j);val pt=point(p)
            if(p!=null&&pt!=null&&match(p.str("time")))current.add(pt)
            else if(current.isNotEmpty()){paths.add(current);current=mutableListOf()}
        }
        if(current.isNotEmpty())paths.add(current)
    }}
    val stops=visits.mapNotNull{point(it.optJSONObject("location"))}
    val ends=acts.flatMap{listOfNotNull(point(it.optJSONObject("first")),point(it.optJSONObject("last")))}
    val view=frame(plans.flatten()+paths.flatten()+stops+ends)
    var bitmap by remember(t.id,day,data,view){mutableStateOf<Bitmap?>(null)}
    var zoom by remember(t.id,day,data){mutableStateOf(1f)}
    var pan by remember(t.id,day,data){mutableStateOf(Offset.Zero)}
    var confirm by remember{mutableStateOf(false)}
    val distances=acts.mapNotNull{it.optDouble("distanceMeters").takeIf{v->v.isFinite()&&v>=0}}
    val minutes=acts.sumOf{a->try{Duration.between(OffsetDateTime.parse(a.str("startTime")),OffsetDateTime.parse(a.str("endTime"))).toMinutes().coerceAtLeast(0)}catch(_:Exception){0L}}
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){
        TextButton(onClick={val i=dates.indexOf(day);day=if(i>0)dates[i-1] else ""},enabled=day.isNotEmpty()&&!busy){Text("‹")}
        Text(if(day.isBlank())"Tutto il viaggio" else day)
        TextButton(onClick={val i=dates.indexOf(day);if(i<dates.lastIndex)day=dates[i+1]},enabled=dates.indexOf(day)<dates.lastIndex&&!busy){Text("›")}
    }
    Text(visits.size.toString()+" visite · "+acts.size+" spostamenti · "+plans.flatten().size+" tappe previste")
    Text((if(distances.isEmpty())"Distanza non disponibile" else String.format(java.util.Locale.ITALY,"%.1f km registrati",distances.sum()/1000))+" · "+minutes+" min negli spostamenti",fontSize=12.sp)
    if(view!=null){
        Row(horizontalArrangement=Arrangement.spacedBy(4.dp)){
            TextButton(onClick={zoom=(zoom*1.4f).coerceAtMost(12f)}){Text("+ Zoom")}
            TextButton(onClick={zoom=(zoom/1.4f).coerceAtLeast(.5f)}){Text("− Zoom")}
            TextButton(onClick={zoom=1f;pan=Offset.Zero}){Text("Centra")}
        }
        Canvas(Modifier.fillMaxWidth().aspectRatio(1f).clipToBounds().background(Color(0xFF162C3F)).pointerInput(day,data){
            detectDragGestures{change,drag->change.consume();pan+=drag}
        }){
            val k=size.width/768f
            withTransform({translate(pan.x,pan.y);scale(zoom,zoom,center)}){
                bitmap?.let{drawImage(it.asImageBitmap(),dstOffset=IntOffset.Zero,dstSize=IntSize(size.width.toInt(),size.height.toInt()))}
                fun drawLine(points:List<DiaryPoint>,color:Color,dashed:Boolean){
                    val coords=points.map{view.project(it)*k}
                    if(coords.size==1)drawCircle(color,4f,coords.first())
                    else if(coords.isNotEmpty()){
                        val p=Path().apply{moveTo(coords.first().x,coords.first().y);coords.drop(1).forEach{lineTo(it.x,it.y)}}
                        drawPath(p,color,style=Stroke(width=3f,pathEffect=if(dashed)PathEffect.dashPathEffect(floatArrayOf(8f,5f)) else null))
                    }
                }
                plans.forEach{p->drawLine(p,Color(0xFF008B88),true);p.forEach{drawCircle(Color(0xFF008B88),5f,view.project(it)*k)}}
                paths.forEach{drawLine(it,Color(0xFFE58617),false)}
                stops.forEach{drawCircle(Color(0xFFFFBE55),6f,view.project(it)*k)}
                ends.forEach{drawCircle(Color(0xFFA5B4FC),3f,view.project(it)*k)}
            }
        }
        if(loadMap!=null)TextButton(onClick={confirm=true},enabled=!busy){Text("Carica cartografia Geoapify")}
        if(bitmap!=null)Text("Geoapify · © OpenMapTiles · © OpenStreetMap contributors",fontSize=10.sp)
        if(confirm)AlertDialog(onDismissRequest={confirm=false},title={Text("Caricare la cartografia?")},text={Text("Geoapify riceverà gli indici delle tessere dell’area, non la cronologia o le visite.")},
            confirmButton={TextButton(onClick={confirm=false;loadMap?.invoke(view.z,view.tileX,view.y){bitmap=it}}){Text("Carica")}},dismissButton={TextButton(onClick={confirm=false}){Text("Annulla")}})
        Text("Verde: tappe previste (collegamenti schematici). Arancione: percorso registrato. Giallo: visite. Lilla: estremi. Nessuna ricostruzione dei tratti mancanti.",fontSize=11.sp)
    }
    if(data==null)Text("Nessuna cronologia disponibile.")
    val events=(visits.map{it to "Visita"}+acts.map{it to "Spostamento"}).sortedBy{it.first.str("startTime")}
    for((v,label) in events.take(200)){
        HorizontalDivider()
        Text(label+" · "+v.str("startTime").take(16).replace('T',' '))
        val location=point(v.optJSONObject("location"))
        Text(if(location!=null)location.lat.toString()+", "+location.lon else v.str("mode")+" · "+v.str("endTime").take(16).replace('T',' '),fontSize=12.sp)
    }
    if(events.size>200)Text("Mostrati i primi 200 eventi: filtra per giorno.")
    if(day.isNotBlank()){
        t.days.firstOrNull{it.str("date")==day}?.arr("route_points")?.forEach{Text("Previsto: "+it.str("label"),fontSize=12.sp)}
        val note=t.state.optJSONObject("notes")?.str(day).orEmpty()
        if(note.isNotBlank())Text("Note: "+note)
    }
}
