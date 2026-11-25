package uk.archis.nextdoviaggi

import androidx.compose.foundation.background
import androidx.compose.foundation.Image
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.runtime.*
import android.graphics.BitmapFactory
import android.util.Base64
import org.json.JSONObject
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.temporal.TemporalAdjusters
import java.time.DayOfWeek
import java.util.Locale

internal enum class NextDoArea(val subtitle:String) {
    HOME("DASHBOARD"), WORK("PROFESSIONALE"), PERSONAL("PERSONALE"), TRIPS("PERSONALE · VIAGGI"), SETTINGS("IMPOSTAZIONI")
}
private val ShellPanel=Color(0xFF172B3D)
private val ShellMuted=Color(0xFFADC1D2)
private val ShellWhite=Color(0xFFF3F8FC)
private val WorkBlue=Color(0xFF83B6FF)
private val PrivateTeal=Color(0xFF69E0D2)
private val ShellSand=Color(0xFFFFD49A)

@Composable
internal fun NextDoNavigation(area:NextDoArea,enabled:Boolean,open:(NextDoArea)->Unit) {
    val destinations=listOf(
        Triple(NextDoArea.HOME,"Home",Icons.Default.Home),
        Triple(NextDoArea.WORK,"Lavoro",Icons.Default.Work),
        Triple(NextDoArea.PERSONAL,"Personale",Icons.Default.Person),
        Triple(NextDoArea.SETTINGS,"Impostazioni",Icons.Default.Settings))
    NavigationBar(containerColor=ShellPanel) {
        destinations.forEach{(target,label,icon)->
            val selected=area==target||(area==NextDoArea.TRIPS&&target==NextDoArea.PERSONAL)
            val accent=if(target==NextDoArea.WORK)WorkBlue else PrivateTeal
            NavigationBarItem(selected=selected,enabled=enabled,onClick={open(target)},
                icon={Icon(icon,label)},label={Text(label,fontSize=10.sp,maxLines=1)},
                colors=NavigationBarItemDefaults.colors(indicatorColor=accent.copy(alpha=.18f),selectedIconColor=accent,selectedTextColor=accent,unselectedIconColor=ShellMuted,unselectedTextColor=ShellMuted))
        }
    }
}
@Composable
private fun ShellCard(title:String,subtitle:String,icon:ImageVector,accent:Color,enabled:Boolean=true,action:(()->Unit)?=null,content:@Composable ColumnScope.()->Unit={}) {
    Card(Modifier.fillMaxWidth(),shape=RoundedCornerShape(24.dp),colors=CardDefaults.cardColors(containerColor=ShellPanel)){
        Column(Modifier.padding(18.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){
            Row(Modifier.fillMaxWidth().then(if(action!=null)Modifier.clickable(enabled=enabled,onClick=action) else Modifier),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(12.dp)){
                Box(Modifier.size(48.dp).clip(RoundedCornerShape(15.dp)).background(accent.copy(alpha=.13f)),contentAlignment=Alignment.Center){
                    Icon(icon,null,Modifier.size(25.dp),tint=accent)
                }
                Column(Modifier.weight(1f)){
                    Text(title,color=ShellWhite,fontWeight=FontWeight.Bold,fontSize=20.sp)
                    Text(subtitle,color=ShellMuted,fontSize=12.sp,lineHeight=17.sp)
                }
                if(action!=null)Icon(Icons.Default.ChevronRight,"Apri "+title,tint=accent)
            }
            content()
        }
    }
}
@Composable
private fun StatusTile(label:String,icon:ImageVector,accent:Color,modifier:Modifier=Modifier,value:String="—",enabled:Boolean=true,onClick:(()->Unit)?=null) {
    Column(modifier.clip(RoundedCornerShape(15.dp)).background(accent.copy(alpha=.08f)).then(if(onClick!=null)Modifier.clickable(enabled=enabled,onClick=onClick) else Modifier).padding(12.dp),verticalArrangement=Arrangement.spacedBy(5.dp)){
        Icon(icon,null,tint=accent)
        Text(label,color=ShellWhite,fontWeight=FontWeight.SemiBold,fontSize=13.sp)
        Text(value,color=ShellMuted,fontSize=23.sp)
    }
}
@Composable
internal fun NextDoDashboard(enabled:Boolean,connected:Boolean,hasOffline:Boolean,agenda:WorkAgenda?,workConnected:Boolean,workBusy:Boolean,workError:String,openWork:(String)->Unit,onDetail:(Long)->Unit,onRefresh:()->Unit,open:(NextDoArea)->Unit) {
    Text("La tua dashboard",fontSize=29.sp,fontWeight=FontWeight.ExtraBold,color=ShellWhite)
    Text(LocalDate.now().format(DateTimeFormatter.ofPattern("EEEE d MMMM yyyy",Locale.ITALIAN)),color=ShellMuted,fontSize=14.sp)
    ShellCard("Professionale","Agenda, scadenze e appuntamenti",Icons.Default.Work,WorkBlue,enabled,{open(NextDoArea.WORK)}) {
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(10.dp)){
            StatusTile("Scadenze",Icons.Default.Event,WorkBlue,Modifier.weight(1f),agenda?.items?.count{it.kind=="task"}?.toString()?:"—",enabled){openWork("tasks")}
            StatusTile("Appuntamenti",Icons.Default.CalendarToday,WorkBlue,Modifier.weight(1f),agenda?.items?.count{it.kind=="appointment"}?.toString()?:"—",enabled){openWork("appointments")}
        }
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(10.dp)){
            StatusTile("Urgenti",Icons.Default.Warning,ShellSand,Modifier.weight(1f),agenda?.items?.count{it.urgent}?.toString()?:"—",enabled){openWork("urgent")}
            StatusTile("Da verificare",Icons.Default.FactCheck,WorkBlue,Modifier.weight(1f),agenda?.items?.count{it.status=="review"}?.toString()?:"—",enabled){openWork("review")}
        }
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(10.dp)){
            StatusTile("Da fare",Icons.Default.Checklist,WorkBlue,Modifier.weight(1f),agenda?.items?.count{it.status=="todo"}?.toString()?:"—",enabled){openWork("todo")}
            StatusTile("Senza data",Icons.Default.EventBusy,ShellSand,Modifier.weight(1f),agenda?.items?.count{it.day.isBlank()}?.toString()?:"—",enabled){openWork("undated")}
        }
        if(workError.isNotBlank())Text(workError,color=ShellSand,fontSize=12.sp)
        if(workConnected)TextButton(onClick=onRefresh,enabled=!workBusy&&enabled){Text("Aggiorna agenda")}
        Text(when{workBusy->"Aggiornamento agenda…";agenda!=null->"Ultima sincronizzazione: "+agenda.updated.take(16).replace('T',' ');workConnected->"Agenda non disponibile. Apri Lavoro per riprovare.";else->"Associa l’area professionale. I trattini non indicano assenza di impegni."},color=ShellMuted,fontSize=12.sp)
        agenda?.let{data->
            val entries=orderedWork(data.items)
            HorizontalDivider(color=ShellMuted.copy(alpha=.2f))
            Text("Attività aperte · "+entries.size,color=WorkBlue,fontWeight=FontWeight.Bold)
            if(entries.isEmpty())Text("Nessuna attività aperta",color=ShellMuted,fontSize=13.sp)
            var limit by androidx.compose.runtime.remember{androidx.compose.runtime.mutableIntStateOf(20)}
            for(t in entries.take(limit)){
                Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(8.dp)).clickable(enabled=enabled&&!workBusy){onDetail(t.id)}.padding(vertical=8.dp,horizontal=4.dp),verticalAlignment=Alignment.CenterVertically){
                    Column(Modifier.weight(1f)){
                        Text(t.title,color=ShellWhite,fontWeight=FontWeight.SemiBold,fontSize=14.sp)
                        Text((if(t.kind=="appointment")"Appuntamento" else "Attività")+" · "+t.timeLabel+" · "+statusName(t.status)+(if(t.overdue)if(t.kind=="appointment")" · Trascorso" else " · Scaduta" else ""),color=if(t.overdue||t.status=="review"||t.urgent)ShellSand else ShellMuted,fontSize=11.sp)
                    }
                    Icon(Icons.Default.ChevronRight,"Apri dettaglio",tint=WorkBlue)
                }
            }
            if(entries.size>limit)TextButton(onClick={limit+=20}){Text("Mostra altre "+minOf(20,entries.size-limit)+" voci")}
        }
        OutlinedButton(onClick={openWork("all")},enabled=enabled,modifier=Modifier.fillMaxWidth()){Text("Tutte le attività",color=WorkBlue)}
        TextButton(onClick={openWork("week")},enabled=enabled,modifier=Modifier.fillMaxWidth()){Text("Agenda della settimana",color=WorkBlue)}
    }
    ShellCard("Personale","Il tuo spazio riservato",Icons.Default.Person,PrivateTeal,enabled,{open(NextDoArea.PERSONAL)}) {
        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(10.dp)){
            Icon(Icons.Default.Flight,null,tint=PrivateTeal)
            Column(Modifier.weight(1f)){
                Text("Viaggi",fontWeight=FontWeight.SemiBold,color=ShellWhite)
                Text(when{connected->"Archivio online";hasOffline->"Copia offline disponibile";else->"Collega o sblocca Viaggi"},fontSize=12.sp,color=ShellMuted)
            }
            TextButton(onClick={open(NextDoArea.TRIPS)},enabled=enabled){Text("Apri")}
        }
    }
}
@Composable
internal fun PersonalLanding(enabled:Boolean,appearance:JSONObject?,connected:Boolean,problem:String,photoPending:Boolean,save:(JSONObject)->Unit,choosePhoto:()->Unit,uploadPhoto:()->Unit,openTrips:()->Unit) {
    val theme=appearance?.optString("theme","dark")?:"dark"
    val palette=appearance?.optString("palette","ocean")?:"ocean"
    val background=appearance?.optString("background","gradient")?:"gradient"
    val light=theme=="light"
    val accent=when(palette){"forest"->Color(0xFF9EE0A3);"sunset"->Color(0xFFFFD49A);"lavender"->Color(0xFFCBBaff);else->PrivateTeal}
    val start=when(palette){"forest"->Color(0xFF183F37);"sunset"->Color(0xFF663A55);"lavender"->Color(0xFF39376D);else->Color(0xFF163651)}
    val end=when(palette){"forest"->Color(0xFF44784B);"sunset"->Color(0xFFB26B45);"lavender"->Color(0xFF7463A7);else->Color(0xFF176E71)}
    val cardColor=if(light)Color.White else ShellPanel
    val textColor=if(light)Color(0xFF172B3D) else ShellWhite
    val muted=if(light)Color(0xFF475569) else ShellMuted
    val jpeg=appearance?.optString("photo","")?.takeIf{it!="null"}.orEmpty()
    val bitmap=remember(jpeg,background){if(background=="photo"&&jpeg.length<=650000&&jpeg.isNotBlank())runCatching{val bytes=Base64.decode(jpeg,Base64.DEFAULT);BitmapFactory.decodeByteArray(bytes,0,bytes.size)?.asImageBitmap()}.getOrNull()else null}
    var customize by remember { mutableStateOf(false) }
    var selectedTheme by remember(theme){mutableStateOf(theme)}
    var selectedPalette by remember(palette){mutableStateOf(palette)}
    var selectedBackground by remember(background){mutableStateOf(background)}
    Box(Modifier.fillMaxWidth().height(200.dp).clip(RoundedCornerShape(26.dp)).background(Brush.linearGradient(listOf(start,if(background=="plain")start else end)))){
        bitmap?.let { Image(it,null,Modifier.fillMaxSize(),contentScale=ContentScale.Crop);Box(Modifier.fillMaxSize().background(Color(0x99071526))) }
        Column(Modifier.align(Alignment.BottomStart).padding(24.dp),verticalArrangement=Arrangement.spacedBy(7.dp)){
            Text("IL TUO SPAZIO",color=Color.White,fontSize=11.sp,fontWeight=FontWeight.Bold)
            Text("Area personale",color=Color.White,fontSize=30.sp,fontWeight=FontWeight.ExtraBold)
            Text("Il tuo tempo, i tuoi impegni e i tuoi viaggi.",color=Color.White,fontSize=14.sp)
        }
    }
    Card(colors=CardDefaults.cardColors(containerColor=cardColor),shape=RoundedCornerShape(18.dp)){
        Column(Modifier.fillMaxWidth().padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
            TextButton(onClick={customize=!customize},enabled=enabled){Text(if(customize)"Chiudi personalizzazione" else "Personalizza il tuo spazio",color=if(light)start else accent)}
            if(problem.isNotBlank())Text(problem,color=muted,fontSize=12.sp)
            if(customize){
                if(!connected)Text("Collega e sblocca Viaggi per sincronizzare le preferenze.",color=muted,fontSize=13.sp)
                Text("Tema",color=textColor,fontWeight=FontWeight.SemiBold)
                Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
                    for((key,label) in listOf("dark" to "Scuro","light" to "Chiaro"))FilterChip(selectedTheme==key,{selectedTheme=key},{Text(label)},enabled=enabled&&connected)
                }
                Text("Colore",color=textColor,fontWeight=FontWeight.SemiBold)
                for(row in listOf(listOf("ocean" to "Oceano","forest" to "Bosco"),listOf("sunset" to "Tramonto","lavender" to "Lavanda"))){
                    Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){for((key,label) in row)FilterChip(selectedPalette==key,{selectedPalette=key},{Text(label)},enabled=enabled&&connected)}
                }
                Text("Sfondo",color=textColor,fontWeight=FontWeight.SemiBold)
                Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){
                    for((key,label) in listOf("gradient" to "Sfumatura","plain" to "Tinta unita"))FilterChip(selectedBackground==key,{selectedBackground=key},{Text(label)},enabled=enabled&&connected)
                }
                if(jpeg.isNotBlank())FilterChip(selectedBackground=="photo",{selectedBackground="photo"},{Text("Fotografia")},enabled=enabled&&connected)
                Button(onClick={save(JSONObject().put("theme",selectedTheme).put("palette",selectedPalette).put("background",selectedBackground))},enabled=enabled&&connected,modifier=Modifier.fillMaxWidth(),colors=ButtonDefaults.buttonColors(containerColor=accent,contentColor=Color(0xFF10212B))){Text("Salva aspetto")}
                OutlinedButton(onClick=choosePhoto,enabled=enabled&&connected,modifier=Modifier.fillMaxWidth()){Text("Scegli fotografia",color=if(light)start else accent)}
                if(photoPending)Button(onClick=uploadPhoto,enabled=enabled&&connected,modifier=Modifier.fillMaxWidth()){Text("Carica fotografia selezionata")}
                if(jpeg.isNotBlank())TextButton(onClick={save(JSONObject().put("clear_photo",true))},enabled=enabled&&connected){Text("Rimuovi fotografia",color=if(light)start else accent)}
                TextButton(onClick={save(JSONObject().put("theme","dark").put("palette","ocean").put("background","gradient").put("clear_photo",true))},enabled=enabled&&connected){Text("Ripristina aspetto",color=if(light)start else accent)}
            }
        }
    }
    for((title,subtitle,icon) in listOf(
        Triple("Viaggi","Itinerari, prenotazioni, PDF, guide e Diario di bordo",Icons.Default.Flight),
        Triple("Attività","Da sviluppare",Icons.Default.Checklist),
        Triple("Scadenze","Da sviluppare",Icons.Default.Event),
        Triple("Appuntamenti","Da sviluppare",Icons.Default.CalendarToday))){
        Card(Modifier.fillMaxWidth(),shape=RoundedCornerShape(22.dp),colors=CardDefaults.cardColors(containerColor=cardColor)){
            Row(Modifier.fillMaxWidth().then(if(title=="Viaggi")Modifier.clickable(enabled=enabled,onClick=openTrips) else Modifier).padding(18.dp),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(14.dp)){
                Box(Modifier.size(48.dp).clip(RoundedCornerShape(14.dp)).background(start),contentAlignment=Alignment.Center){Icon(icon,null,tint=accent)}
                Column(Modifier.weight(1f)){Text(title,color=textColor,fontWeight=FontWeight.Bold,fontSize=19.sp);Text(subtitle,color=muted,fontSize=12.sp)}
                if(title=="Viaggi")Icon(Icons.Default.ChevronRight,"Apri Viaggi",tint=if(light)start else accent)
            }
        }
    }
}
