package uk.archis.nextdoviaggi

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import java.time.LocalDate
import java.time.YearMonth
import java.time.format.DateTimeFormatter
import java.util.Locale

internal enum class NextDoArea(val subtitle:String) {
    HOME("DASHBOARD"), WORK("PROFESSIONALE"), PERSONAL("PERSONALE"), TRIPS("PERSONALE · VIAGGI"), SETTINGS("IMPOSTAZIONI")
}
internal val ShellPanel=Color(0xFF10283D)
internal val ShellMuted=Color(0xFFABC1D5)
internal val ShellWhite=Color(0xFFF2F7FC)
internal val WorkBlue=Color(0xFF75BBFF)
internal val PrivateTeal=Color(0xFF50DED0)
internal val ShellSand=Color(0xFFFFC773)
internal val ShellRed=Color(0xFFFF8999)
internal val ShellPurple=Color(0xFFC1A9FF)
internal val ShellGreen=Color(0xFF80E3AF)

@Composable
internal fun NextDoNavigation(area:NextDoArea,enabled:Boolean,open:(NextDoArea)->Unit) {
    val destinations=listOf(
        Triple(NextDoArea.HOME,"Home",Icons.Default.Home),
        Triple(NextDoArea.WORK,"Lavoro",Icons.Default.Work),
        Triple(NextDoArea.PERSONAL,"Personale",Icons.Default.Person),
        Triple(NextDoArea.SETTINGS,"Impostazioni",Icons.Default.Settings))
    NavigationBar(containerColor=Color(0xFF0A2032),tonalElevation=0.dp) {
        destinations.forEach{(target,label,icon)->
            val selected=area==target||(area==NextDoArea.TRIPS&&target==NextDoArea.PERSONAL)
            val accent=if(target==NextDoArea.WORK)WorkBlue else PrivateTeal
            NavigationBarItem(selected=selected,enabled=enabled,onClick={open(target)},
                icon={Icon(icon,label,Modifier.size(22.dp))},label={Text(label,fontSize=10.sp,maxLines=1)},
                colors=NavigationBarItemDefaults.colors(indicatorColor=accent.copy(alpha=.18f),selectedIconColor=accent,selectedTextColor=accent,unselectedIconColor=ShellMuted,unselectedTextColor=ShellMuted))
        }
    }
}

@Composable
internal fun BentoCard(title:String,icon:ImageVector,accent:Color=PrivateTeal,subtitle:String="",action:(()->Unit)?=null,content:@Composable ColumnScope.()->Unit={}) {
    Card(Modifier.fillMaxWidth(),shape=RoundedCornerShape(16.dp),border=BorderStroke(1.dp,accent.copy(alpha=.18f)),colors=CardDefaults.cardColors(containerColor=ShellPanel)){
        Column(Modifier.padding(12.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
            Row(Modifier.fillMaxWidth().then(if(action!=null)Modifier.clip(RoundedCornerShape(8.dp)).clickable(onClick=action).heightIn(min=48.dp) else Modifier),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(9.dp)){
                Box(Modifier.size(32.dp).clip(RoundedCornerShape(10.dp)).background(accent.copy(alpha=.12f)),contentAlignment=Alignment.Center){Icon(icon,null,Modifier.size(20.dp),tint=accent)}
                Column(Modifier.weight(1f)){
                    Text(title,color=ShellWhite,fontWeight=FontWeight.Bold,fontSize=17.sp,lineHeight=21.sp)
                    if(subtitle.isNotBlank())Text(subtitle,color=ShellMuted,fontSize=12.sp,lineHeight=16.sp)
                }
                if(action!=null)Icon(Icons.Default.ChevronRight,"Apri "+title,tint=accent)
            }
            content()
        }
    }
}

@Composable
internal fun StatusTile(label:String,icon:ImageVector,accent:Color,modifier:Modifier=Modifier,value:String="—",enabled:Boolean=true,selected:Boolean=false,onClick:(()->Unit)?=null) {
    Surface(modifier.then(if(onClick!=null)Modifier.clip(RoundedCornerShape(13.dp)).clickable(enabled=enabled,onClick=onClick) else Modifier),
        color=if(selected)accent.copy(alpha=.19f) else ShellPanel,shape=RoundedCornerShape(13.dp),border=BorderStroke(1.dp,accent.copy(alpha=if(selected).75f else .21f))){
        Column(Modifier.heightIn(min=82.dp).padding(9.dp),verticalArrangement=Arrangement.spacedBy(3.dp)){
            Icon(icon,null,Modifier.size(20.dp),tint=accent)
            Text(label,color=ShellWhite,fontWeight=FontWeight.SemiBold,fontSize=11.sp,lineHeight=13.sp,maxLines=2,overflow=TextOverflow.Ellipsis)
            Text(value,color=ShellWhite,fontSize=24.sp,lineHeight=27.sp,fontWeight=FontWeight.Bold)
        }
    }
}

internal fun shortDate(day:String):String=runCatching{LocalDate.parse(day).format(DateTimeFormatter.ofPattern("d MMM",Locale.ITALIAN))}.getOrDefault(day)

@Composable
internal fun WorkItemRow(t:WorkItem,enabled:Boolean=true,onDetail:(Long)->Unit,onAck:((Long,String)->Unit)?=null){
    val accent=when{t.overdue->ShellRed;t.status=="review"||t.urgent->ShellSand;t.kind=="appointment"->WorkBlue;else->PrivateTeal}
    val date=runCatching{LocalDate.parse(t.day)}.getOrNull()
    Column(Modifier.fillMaxWidth()){
        Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).clickable(enabled=enabled){onDetail(t.id)}.heightIn(min=64.dp).background(Color(0xFF0A2032)).padding(8.dp),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(10.dp)){
            Box(Modifier.width(49.dp).heightIn(min=54.dp).clip(RoundedCornerShape(9.dp)).background(accent.copy(alpha=.12f)),contentAlignment=Alignment.Center){
                Column(Modifier.padding(4.dp),horizontalAlignment=Alignment.CenterHorizontally){
                    if(date!=null){
                        Text(date.format(DateTimeFormatter.ofPattern("EEE",Locale.ITALIAN)).uppercase(Locale.ITALIAN),color=accent,fontSize=10.sp,lineHeight=12.sp)
                        Text(date.dayOfMonth.toString(),color=ShellWhite,fontSize=21.sp,lineHeight=23.sp,fontWeight=FontWeight.Bold)
                        Text(date.format(DateTimeFormatter.ofPattern("MMM",Locale.ITALIAN)).uppercase(Locale.ITALIAN),color=ShellMuted,fontSize=10.sp,lineHeight=12.sp)
                    }else Icon(Icons.Default.EventBusy,"Senza data",tint=accent)
                }
            }
            Column(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(3.dp)){
                val label=if(t.day.isBlank())"Senza data" else if(t.instant.isNotBlank())t.instant.drop(11).take(5) else if(t.kind=="appointment")"Orario da definire" else "Scadenza"
                Text(label,color=accent,fontSize=11.sp,fontWeight=FontWeight.SemiBold)
                Text(t.title,color=ShellWhite,fontSize=14.sp,lineHeight=18.sp,fontWeight=FontWeight.SemiBold,maxLines=2,overflow=TextOverflow.Ellipsis)
                Text((if(t.kind=="appointment")"Appuntamento" else "Attività")+" · "+statusName(t.status)+(if(t.overdue) " · Trascorsa" else ""),color=if(t.status=="review"||t.overdue)accent else ShellMuted,fontSize=11.sp,lineHeight=14.sp)
            }
            Icon(Icons.Default.ChevronRight,"Apri dettaglio",Modifier.size(19.dp),tint=accent)
        }
        if(onAck!=null)Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.End,verticalAlignment=Alignment.CenterVertically){
            if(t.acknowledged)Text("Presa visione sincronizzata",color=WorkBlue,fontSize=11.sp)
            else TextButton(onClick={onAck(t.id,t.revision)},enabled=enabled){Text("Presa visione",fontSize=12.sp)}
        }
    }
}

internal fun monthCells(month:YearMonth):List<LocalDate>{
    val first=month.atDay(1);val offset=first.dayOfWeek.value-1
    return List(42){first.minusDays(offset.toLong()).plusDays(it.toLong())}
}

@Composable
internal fun BentoCalendar(today:LocalDate,marked:Set<String>,review:Set<String> = emptySet(),selected:String="",onDay:(LocalDate)->Unit,title:String="Calendario"){
    var month by remember(today){mutableStateOf(YearMonth.from(today))}
    BentoCard(title,Icons.Default.CalendarMonth,WorkBlue){
        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.SpaceBetween){
            IconButton(onClick={month=month.minusMonths(1)}){Icon(Icons.Default.ChevronLeft,"Mese precedente",tint=WorkBlue)}
            Text(month.format(DateTimeFormatter.ofPattern("MMMM yyyy",Locale.ITALIAN)),color=ShellWhite,fontSize=15.sp,fontWeight=FontWeight.Bold)
            IconButton(onClick={month=month.plusMonths(1)}){Icon(Icons.Default.ChevronRight,"Mese successivo",tint=WorkBlue)}
        }
        Row(Modifier.fillMaxWidth()){
            listOf("Lun","Mar","Mer","Gio","Ven","Sab","Dom").forEach{Text(it,Modifier.weight(1f),color=ShellMuted,fontSize=10.sp,textAlign=androidx.compose.ui.text.style.TextAlign.Center)}
        }
        for(week in monthCells(month).chunked(7)){
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(2.dp)){
                for(day in week){
                    val ds=day.toString()
                    val active=ds==selected||day==today
                    val fg=if(active)Color(0xFF061A27) else if(YearMonth.from(day)==month)ShellWhite else ShellMuted.copy(alpha=.65f)
                    Column(Modifier.weight(1f).heightIn(min=43.dp).clip(RoundedCornerShape(9.dp)).background(if(active)PrivateTeal else if(ds in marked)WorkBlue.copy(alpha=.10f) else Color.Transparent)
                        .clickable{onDay(day)}.padding(vertical=4.dp),horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.Center){
                        Text(day.dayOfMonth.toString(),color=fg,fontWeight=if(active)FontWeight.Bold else FontWeight.Medium,fontSize=13.sp)
                        Box(Modifier.padding(top=2.dp).size(5.dp).clip(RoundedCornerShape(50)).background(if(ds in review)ShellSand else if(ds in marked)if(active)Color(0xFF1766B4) else WorkBlue else Color.Transparent))
                    }
                }
            }
        }
        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
            Text("• Impegno   • Da verificare",Modifier.weight(1f),color=ShellMuted,fontSize=11.sp)
            TextButton(onClick={month=YearMonth.from(today)}){Text("Oggi")}
        }
    }
}

@Composable
private fun AgendaBlock(title:String,subtitle:String,items:List<WorkItem>,accent:Color,enabled:Boolean,onMore:()->Unit,onDetail:(Long)->Unit){
    BentoCard(title,Icons.Default.Event,accent,subtitle,if(enabled)onMore else null){
        if(items.isEmpty())Text("Nessun impegno",color=ShellMuted,fontSize=12.sp)
        for(t in orderedWork(items).take(3))WorkItemRow(t,enabled,onDetail)
        if(items.size>3)TextButton(onClick=onMore,enabled=enabled){Text("Vedi tutti ("+items.size+")")}
    }
}

@Composable
internal fun NextDoDashboard(enabled:Boolean,connected:Boolean,hasOffline:Boolean,agenda:WorkAgenda?,workConnected:Boolean,workBusy:Boolean,workError:String,openWork:(String)->Unit,onDetail:(Long)->Unit,onRefresh:()->Unit,open:(NextDoArea)->Unit) {
    val today=runCatching{LocalDate.parse(agenda?.today.orEmpty())}.getOrDefault(LocalDate.now())
    val items=agenda?.items.orEmpty()
    val ready=agenda!=null
    val allowed=enabled&&!workBusy
    val title=agenda?.name?.trim()?.takeIf{it.isNotBlank()}?.let{"Ciao, "+it} ?: "Centro operativo"
    Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
        Column(Modifier.weight(1f)){
            Text(title,fontSize=23.sp,lineHeight=28.sp,fontWeight=FontWeight.ExtraBold,color=ShellWhite)
            Text(today.format(DateTimeFormatter.ofPattern("EEEE d MMMM yyyy",Locale.ITALIAN)),color=ShellMuted,fontSize=13.sp)
        }
        IconButton(onClick=onRefresh,enabled=workConnected&&allowed){Icon(Icons.Default.Refresh,"Aggiorna agenda",tint=WorkBlue)}
    }
    if(workBusy)LinearProgressIndicator(Modifier.fillMaxWidth(),color=PrivateTeal)
    if(workError.isNotBlank())Text(workError,color=ShellSand,fontSize=12.sp)
    if(!ready)BentoCard("Agenda professionale",Icons.Default.Work,WorkBlue,if(workConnected)"Agenda non disponibile" else "Associa il dispositivo",action={open(NextDoArea.WORK)}){}
    val tiles=listOf(
        Triple("Scadenze",Icons.Default.Event,"tasks"),Triple("Appuntamenti",Icons.Default.CalendarToday,"appointments"),Triple("Urgenti",Icons.Default.Warning,"urgent"),
        Triple("Da fare",Icons.Default.Checklist,"todo"),Triple("Da verificare",Icons.Default.FactCheck,"review"),Triple("Senza data",Icons.Default.EventBusy,"undated"))
    for(row in tiles.chunked(3)){
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(7.dp)){
            for((label,icon,filter) in row){
                val accent=when(filter){"urgent","review","undated"->ShellSand;"appointments"->WorkBlue;else->PrivateTeal}
                StatusTile(label,icon,accent,Modifier.weight(1f),if(ready)items.count{workMatches(it,filter)}.toString() else "—",allowed){openWork(filter)}
            }
        }
    }
    agenda?.completion?.let{completed->
        BentoCard("Completate · "+completionLabel(completed.period),Icons.Default.CheckCircle,ShellGreen,
            completed.count.toString()+" attività nel periodo",action=if(allowed){{openWork("completed")}} else null){}
    }
    if(ready){
        val late=items.filter{it.overdue}
        if(late.isNotEmpty())AgendaBlock("Scadute / trascorsi",late.size.toString()+" da gestire",late,ShellRed,allowed,{openWork("overdue")},onDetail)
        for((offset,label) in listOf(0L to "Oggi",1L to "Domani")){
            val day=today.plusDays(offset)
            AgendaBlock(label,shortDate(day.toString()),items.filter{it.day==day.toString()&&!it.overdue},if(offset==0L)PrivateTeal else WorkBlue,allowed,{openWork("day:"+day)},onDetail)
        }
        val future=items.filter{it.day>today.plusDays(1).toString()}
        AgendaBlock("Prossimi impegni",future.size.toString()+" in arrivo",future,WorkBlue,allowed,{openWork("future")},onDetail)
        val review=items.filter{it.status=="review"&&it.day.isBlank()}
        if(review.isNotEmpty())AgendaBlock("Da verificare · senza data","",review,ShellSand,allowed,{openWork("review")},onDetail)
        val undated=items.filter{it.day.isBlank()&&it.status!="review"}
        if(undated.isNotEmpty())AgendaBlock("Attività senza data","",undated,ShellSand,allowed,{openWork("undated")},onDetail)
        BentoCalendar(today,items.mapNotNull{it.day.takeIf(String::isNotBlank)}.toSet(),items.filter{it.status=="review"}.map{it.day}.toSet(),onDay={openWork("day:"+it)})
        Text("Sincronizzazione: "+agenda!!.updated.take(16).replace('T',' '),color=ShellMuted,fontSize=11.sp)
    }
    OutlinedButton(onClick={openWork("all")},enabled=allowed,modifier=Modifier.fillMaxWidth()){Text("Tutte le attività",color=WorkBlue)}
    BentoCard("Personale",Icons.Default.Person,PrivateTeal,"Il tuo spazio riservato",action={open(NextDoArea.PERSONAL)}){
        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
            Icon(Icons.Default.Flight,null,tint=PrivateTeal)
            Spacer(Modifier.width(8.dp))
            Text(if(connected)"Viaggi · Archivio online" else if(hasOffline)"Viaggi · Copia offline" else "Viaggi",Modifier.weight(1f),color=ShellWhite,fontSize=13.sp)
            TextButton(onClick={open(NextDoArea.TRIPS)},enabled=enabled){Text("Apri")}
        }
    }
}

@Composable
internal fun PersonalLanding(enabled:Boolean,trips:List<JSONObject>,connected:Boolean,offline:JSONObject?,openTrips:()->Unit,onTrip:(String)->Unit,onOffline:()->Unit) {
    Text("Il tuo spazio personale",fontSize=23.sp,lineHeight=28.sp,fontWeight=FontWeight.ExtraBold,color=ShellWhite)
    BentoCard("Viaggi",Icons.Default.Flight,PrivateTeal,"Itinerari, prenotazioni, documenti e diario",action=if(enabled)openTrips else null){
        Text(if(connected)"Archivio online" else "Archivio riservato",color=ShellMuted,fontSize=12.sp)
        Button(onClick=openTrips,enabled=enabled,modifier=Modifier.fillMaxWidth()){Text("Apri Viaggi")}
    }
    if(connected&&trips.isNotEmpty()){
        Text("I tuoi viaggi",fontSize=17.sp,fontWeight=FontWeight.Bold)
        for(trip in trips){
            BentoCard(trip.str("title").ifBlank{"Viaggio"},Icons.Default.Flight,WorkBlue,
                listOf(trip.str("start"),trip.str("end")).filter{it.isNotBlank()}.joinToString(" — "),
                action=if(enabled){{onTrip(trip.str("id"))}} else null){}
        }
    }
    offline?.let{BentoCard("Copia offline",Icons.Default.DownloadDone,ShellGreen,it.str("title")+" · "+it.optInt("pdfs")+" PDF",action=if(enabled)onOffline else null){}}
    BentoCard("Altre funzioni personali",Icons.Default.Person,ShellMuted,"Non ancora disponibili nell'app"){
        Text("Agenda personale, promemoria e note: in sviluppo.",fontSize=12.sp,color=ShellMuted)
    }
}
