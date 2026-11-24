package uk.archis.nextdoviaggi

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
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
private fun StatusTile(label:String,icon:ImageVector,accent:Color,modifier:Modifier=Modifier,value:String="—") {
    Column(modifier.clip(RoundedCornerShape(15.dp)).background(accent.copy(alpha=.08f)).padding(12.dp),verticalArrangement=Arrangement.spacedBy(5.dp)){
        Icon(icon,null,tint=accent)
        Text(label,color=ShellWhite,fontWeight=FontWeight.SemiBold,fontSize=13.sp)
        Text(value,color=ShellMuted,fontSize=23.sp)
    }
}
@Composable
internal fun NextDoDashboard(enabled:Boolean,connected:Boolean,hasOffline:Boolean,agenda:WorkAgenda?,workConnected:Boolean,workBusy:Boolean,open:(NextDoArea)->Unit) {
    Text("La tua dashboard",fontSize=29.sp,fontWeight=FontWeight.ExtraBold,color=ShellWhite)
    Text(LocalDate.now().format(DateTimeFormatter.ofPattern("EEEE d MMMM yyyy",Locale.ITALIAN)),color=ShellMuted,fontSize=14.sp)
    ShellCard("Professionale","Agenda, scadenze e appuntamenti",Icons.Default.Work,WorkBlue,enabled,{open(NextDoArea.WORK)}) {
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(10.dp)){
            StatusTile("Scadenze",Icons.Default.Event,WorkBlue,Modifier.weight(1f),agenda?.items?.count{it.kind=="task"}?.toString()?:"—")
            StatusTile("Appuntamenti",Icons.Default.CalendarToday,WorkBlue,Modifier.weight(1f),agenda?.items?.count{it.kind=="appointment"}?.toString()?:"—")
        }
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(10.dp)){
            StatusTile("Urgenti",Icons.Default.Warning,ShellSand,Modifier.weight(1f),agenda?.items?.count{it.urgent}?.toString()?:"—")
            StatusTile("Da verificare",Icons.Default.FactCheck,WorkBlue,Modifier.weight(1f),agenda?.items?.count{it.status=="review"}?.toString()?:"—")
        }
        Text(when{workBusy->"Aggiornamento agenda…";agenda!=null->"Ultima sincronizzazione: "+agenda.updated.take(16).replace('T',' ');workConnected->"Agenda non disponibile. Apri Lavoro per riprovare.";else->"Associa l’area professionale. I trattini non indicano assenza di impegni."},color=ShellMuted,fontSize=12.sp)
        OutlinedButton(onClick={open(NextDoArea.WORK)},enabled=enabled,modifier=Modifier.fillMaxWidth()){Text("Agenda della settimana",color=WorkBlue)}
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
internal fun PersonalLanding(enabled:Boolean,openTrips:()->Unit) {
    Text("Area personale",fontSize=27.sp,fontWeight=FontWeight.ExtraBold,color=ShellWhite)
    ShellCard("Viaggi","Itinerari, prenotazioni, PDF, guide e Diario di bordo",Icons.Default.Flight,PrivateTeal,enabled,openTrips){
        Button(onClick=openTrips,enabled=enabled,modifier=Modifier.fillMaxWidth()){Text("Apri Viaggi")}
    }
    ShellCard("Agenda personale","Da sviluppare",Icons.Default.CalendarToday,PrivateTeal)
    ShellCard("Promemoria","Da sviluppare",Icons.Default.Notifications,PrivateTeal)
    ShellCard("Note personali","Da sviluppare",Icons.Default.EditNote,PrivateTeal)
}
