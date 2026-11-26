package uk.archis.nextdoviaggi

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

internal data class WorkItem(val id:Long,val title:String,val kind:String,val priority:String,val status:String,val day:String,val instant:String,val overdue:Boolean,val revision:String,val acknowledged:Boolean) {
    val urgent get()=priority=="high"||priority=="critical"
    val timeLabel get()=if(day.isBlank())"Data da definire" else ItalianDateTime.date(day)+(if(instant.isNotBlank())" · "+ItalianDateTime.dateTime(instant).substringAfter(" ",instant) else if(kind=="appointment")" · orario da definire" else "")
}
internal data class WorkAgenda(val items:List<WorkItem>,val today:String,val weekStart:String,val timezone:String,val updated:String,val name:String)
internal class WorkApi(private val base:String){
    private val api=TravelApi(base)
    fun pair(code:String):JSONObject {
        val result=api.obj("/work/pair",data=JSONObject().put("code",code.trim()).put("label","Android "+android.os.Build.MODEL.take(60)))
        return JSONObject().put("url",base.trim()).put("token",result.getString("device_token"))
    }
    fun agenda(token:String):WorkAgenda {
        val items=mutableListOf<WorkItem>();var after=0L;var first:JSONObject?=null
        do {
            val page=api.obj("/work/agenda?after="+after,token)
            if(first==null)first=page
            for(t in page.arr("items")){
                items.add(WorkItem(t.getLong("id"),t.str("title"),t.str("kind"),t.str("priority"),t.str("status"),t.str("day"),t.str("instant"),t.optBoolean("overdue"),t.str("revision"),t.optBoolean("acknowledged")))
            }
            if(page.isNull("next_after"))break
            val next=page.getLong("next_after")
            require(next>after&&items.size<=20000){"Agenda troppo grande: sincronizzazione incompleta"}
            after=next
        }while(true)
        val p=first?:error("Agenda non disponibile")
        return WorkAgenda(items,p.str("today"),p.str("week_start"),p.str("timezone"),p.str("updated_at"),p.str("display_name"))
    }
    fun acknowledge(token:String,id:Long,revision:String)=api.obj("/work/agenda/"+id+"/ack",token,JSONObject().put("revision",revision))
    fun detail(token:String,id:Long)=api.obj("/work/agenda/"+id,token)
    fun revoke(token:String)=api.obj("/work/revoke",token,JSONObject())
}
private val Blue=Color(0xFF83B6FF)
private val SandWork=Color(0xFFFFD49A)
private val MutedWork=Color(0xFFADC1D2)
private val PanelWork=Color(0xFF172B3D)
private val RedWork=Color(0xFFFF9595)
internal fun workMatches(t:WorkItem,filter:String):Boolean=when(filter){
    "tasks"->t.kind=="task"
    "appointments"->t.kind=="appointment"
    "todo"->t.status=="todo"
    "urgent"->t.urgent
    "review"->t.status=="review"
    "late"->t.overdue&&t.kind=="task"
    "past"->t.overdue&&t.kind=="appointment"
    "undated"->t.day.isBlank()
    else->true
}
internal fun orderedWork(items:List<WorkItem>)=items.sortedWith(compareBy<WorkItem>{if(it.overdue)0 else if(it.urgent)1 else if(it.status=="review")2 else 3}.thenBy{it.day.ifBlank{"9999"}}.thenBy{it.instant}.thenBy{it.id})
internal fun statusName(value:String)=when(value){"review"->"Da verificare";"todo"->"Da fare";"doing"->"In corso";"waiting"->"In attesa";"done"->"Completata";else->value}
private fun priorityName(value:String)=when(value){"critical"->"Critica";"high"->"Alta";"low"->"Bassa";else->"Normale"}
@Composable
private fun WorkCard(title:String,action:(()->Unit)?=null,body:@Composable ColumnScope.()->Unit){
    Card(Modifier.fillMaxWidth().then(if(action!=null)Modifier.clickable(onClick=action) else Modifier),shape=RoundedCornerShape(20.dp),colors=CardDefaults.cardColors(containerColor=PanelWork)){
        Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
            Text(title,color=Blue,fontWeight=FontWeight.Bold,fontSize=18.sp)
            body()
        }
    }
}
@Composable
internal fun WorkScreen(connected:Boolean,agenda:WorkAgenda?,busy:Boolean,error:String,defaultUrl:String,onPair:(String,String)->Unit,onRefresh:()->Unit,onDetail:(Long)->Unit,onDisconnect:()->Unit,onAck:(Long,String)->Unit,initialFilter:String="all"){
    var url by remember(defaultUrl){mutableStateOf(defaultUrl)}
    var code by remember{mutableStateOf("")}
    var confirm by remember{mutableStateOf(false)}
    var filter by remember(initialFilter){mutableStateOf(initialFilter)}
    var chosen by remember{mutableStateOf("")}
    var offset by remember{mutableIntStateOf(0)}
    var visible by remember(filter,chosen,offset){mutableIntStateOf(50)}
    Text("Agenda professionale",fontSize=27.sp,fontWeight=FontWeight.ExtraBold)
    if(error.isNotBlank())Text(error,color=RedWork,fontSize=13.sp)
    if(busy)LinearProgressIndicator(Modifier.fillMaxWidth())
    if(!connected){
        WorkCard("Associazione dedicata"){
            Text("In NextDo Web, dalla Dashboard, apri NextDo Android · Professionale e genera un codice monouso. L’associazione Viaggi non viene modificata.",color=MutedWork,fontSize=13.sp)
            OutlinedTextField(url,{url=it},label={Text("URL HTTPS NextDo")},singleLine=true,enabled=!busy,modifier=Modifier.fillMaxWidth())
            OutlinedTextField(code,{code=it},label={Text("Codice monouso")},singleLine=true,visualTransformation=PasswordVisualTransformation(),enabled=!busy,modifier=Modifier.fillMaxWidth())
            Button(onClick={val v=code;code="";onPair(url,v)},enabled=!busy&&url.isNotBlank()&&code.isNotBlank()){Text("Associa Professionale")}
        }
        return
    }
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){
        OutlinedButton(onClick=onRefresh,enabled=!busy){Text("Aggiorna")}
        TextButton(onClick={confirm=true},enabled=!busy){Text("Disassocia",color=SandWork)}
    }
    if(confirm)AlertDialog(onDismissRequest={confirm=false},title={Text("Disassociare Professionale?")},text={Text("L’associazione professionale verrà rimossa. Viaggi resta invariato.")},confirmButton={TextButton(onClick={confirm=false;onDisconnect()}){Text("Disassocia")}},dismissButton={TextButton(onClick={confirm=false}){Text("Annulla")}})
    if(agenda==null){Text("Agenda non disponibile: non significa che non ci siano scadenze.",color=MutedWork);return}
    Text(agenda.name+" · "+agenda.timezone,color=MutedWork,fontSize=13.sp)
    Text("Aggiornata: "+ItalianDateTime.dateTime(agenda.updated),color=MutedWork,fontSize=12.sp)
    val monday=LocalDate.parse(agenda.weekStart).plusWeeks(offset.toLong())
    val sunday=monday.plusDays(6)
    val items=agenda.items
    fun inWeek(t:WorkItem)=t.day.isNotBlank()&&t.day>=monday.toString()&&t.day<=sunday.toString()
    WorkCard("Attività aperte"){ 
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(6.dp)){
            OutlinedButton(onClick={filter="todo";chosen=""},modifier=Modifier.weight(1f)){Text("Da fare "+items.count{it.status=="todo"},fontSize=12.sp)}
            OutlinedButton(onClick={filter="tasks";chosen=""},modifier=Modifier.weight(1f)){Text("Scadenze "+items.count{it.kind=="task"},fontSize=12.sp)}
        }
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(6.dp)){
            OutlinedButton(onClick={filter="appointments";chosen=""},modifier=Modifier.weight(1f)){Text("Appuntamenti "+items.count{it.kind=="appointment"},fontSize=12.sp)}
            OutlinedButton(onClick={filter="all";chosen=""},modifier=Modifier.weight(1f)){Text("Tutte "+items.size,fontSize=12.sp)}
        }
    }
    WorkCard("Settimana"){
        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.SpaceBetween){
            TextButton(onClick={offset--;chosen="";filter="week"}){Text("‹")}
            Text(ItalianDateTime.date(monday)+" – "+ItalianDateTime.date(sunday),fontSize=13.sp)
            TextButton(onClick={offset++;chosen="";filter="week"}){Text("›")}
        }
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(3.dp)){
            for(i in 0L..6L){
                val d=monday.plusDays(i);val ds=d.toString();val count=items.count{it.day==ds}
                TextButton(onClick={chosen=if(chosen==ds)"" else ds;filter="week"},modifier=Modifier.weight(1f).clip(RoundedCornerShape(9.dp)).background(if(chosen==ds||ds==agenda.today)Blue.copy(alpha=.17f) else Color(0xFF203449)),contentPadding=PaddingValues(0.dp)){
                    Column(horizontalAlignment=Alignment.CenterHorizontally){
                        Text(d.format(DateTimeFormatter.ofPattern("EEE",Locale.ITALIAN)).take(3),fontSize=9.sp)
                        Text(d.dayOfMonth.toString(),fontWeight=FontWeight.Bold,fontSize=14.sp)
                        Text(count.toString(),color=MutedWork,fontSize=10.sp)
                    }
                }
            }
        }
        DateField("Vai a una data",chosen,{value->chosen=value;filter="week";if(value.isNotBlank())offset=java.time.temporal.ChronoUnit.WEEKS.between(LocalDate.parse(agenda.weekStart),LocalDate.parse(value).with(java.time.temporal.TemporalAdjusters.previousOrSame(java.time.DayOfWeek.MONDAY))).toInt()},clearable=true,fallback=monday)
        TextButton(onClick={offset=0;chosen="";filter="week"}){Text("Torna alla settimana corrente")}
    }
    WorkCard("Sempre in evidenza"){
        val urgent=items.count{it.urgent}
        val review=items.count{it.status=="review"}
        val overdue=items.count{it.overdue&&it.kind=="task"}
        val past=items.count{it.overdue&&it.kind=="appointment"}
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(6.dp)){
            OutlinedButton(onClick={filter="urgent";chosen=""},modifier=Modifier.weight(1f),contentPadding=PaddingValues(5.dp)){Text("Urgenti "+urgent,color=SandWork,fontSize=12.sp)}
            OutlinedButton(onClick={filter="review";chosen=""},modifier=Modifier.weight(1f),contentPadding=PaddingValues(5.dp)){Text("Da verificare "+review,color=SandWork,fontSize=12.sp)}
        }
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(6.dp)){
            OutlinedButton(onClick={filter="late";chosen=""},modifier=Modifier.weight(1f),contentPadding=PaddingValues(5.dp)){Text("Scadute "+overdue,color=RedWork,fontSize=12.sp)}
            OutlinedButton(onClick={filter="past";chosen=""},modifier=Modifier.weight(1f),contentPadding=PaddingValues(5.dp)){Text("App. trascorsi "+past,fontSize=12.sp)}
        }
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(6.dp)){
            OutlinedButton(onClick={filter="all";chosen=""},modifier=Modifier.weight(1f)){Text("Tutte "+items.size,fontSize=12.sp)}
            OutlinedButton(onClick={filter="undated";chosen=""},modifier=Modifier.weight(1f)){Text("Senza data "+items.count{it.day.isBlank()},fontSize=12.sp)}
        }
    }
    val label=when(filter){"tasks"->"Scadenze e attività";"appointments"->"Appuntamenti";"todo"->"Da fare";"urgent"->"Urgenti";"review"->"Da verificare";"late"->"Scadute";"past"->"Appuntamenti trascorsi";"all"->"Tutte le voci aperte";"undated"->"Senza data";else->ItalianDateTime.date(chosen).ifBlank{"Scadenze e appuntamenti della settimana"}}
    val shown=orderedWork(items.filter{t->if(filter=="week")inWeek(t)&&(chosen.isBlank()||t.day==chosen) else workMatches(t,filter)})
    Text(label+" · "+shown.size,fontSize=18.sp,fontWeight=FontWeight.Bold)
    if(shown.isEmpty())Text("Nessuna voce in questo filtro.",color=MutedWork)
    for(t in shown.take(visible)){
        WorkCard(t.title,if(!busy){{onDetail(t.id)}} else null){
            Text((if(t.kind=="appointment")"Appuntamento" else "Scadenza")+" · "+t.timeLabel,color=MutedWork,fontSize=13.sp)
            Text(statusName(t.status)+" · Priorità "+priorityName(t.priority)+(if(t.overdue)if(t.kind=="task")" · Scaduta" else " · Trascorso" else ""),color=if(t.overdue)RedWork else if(t.urgent||t.status=="review")SandWork else Blue,fontSize=12.sp)
            if(t.acknowledged)Text("Presa visione sincronizzata",color=Blue,fontSize=12.sp)
            Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){
                TextButton(onClick={onDetail(t.id)},enabled=!busy){Text("Apri dettaglio")}
                if(!t.acknowledged)TextButton(onClick={onAck(t.id,t.revision)},enabled=!busy){Text("Presa visione")}
            }
        }
    }
    if(visible<shown.size)OutlinedButton(onClick={visible+=50}){Text("Mostra altre voci")}
    Text("Presa visione sincronizzata; non modifica lo stato dell’attività.",color=MutedWork,fontSize=12.sp)
}
@Composable
internal fun WorkDetailDialog(detail:JSONObject,onMap:(Boolean)->Unit,close:()->Unit){
    AlertDialog(onDismissRequest=close,title={Text(detail.str("title"))},text={
        Column(Modifier.heightIn(max=420.dp).verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(8.dp)){
            Text(statusName(detail.str("status"))+" · "+priorityName(detail.str("priority")))
            Text(ItalianDateTime.dateTime(detail.str("due_at"),true).ifBlank{"Data da definire"},color=MutedWork)
            if(detail.str("kind")=="appointment"&&detail.str("address").isNotBlank()){
                Text(detail.str("address"),color=MutedWork)
                Row{TextButton(onClick={onMap(false)}){Text("Apri in Maps")};TextButton(onClick={onMap(true)}){Text("Naviga")}}
            }
            Text(detail.str("description").take(12000).ifBlank{"Nessuna descrizione"})
            if(detail.str("description").length>12000)Text("Descrizione lunga: consulta il testo completo sul web.",fontSize=12.sp)
        }
    },confirmButton={TextButton(onClick=close){Text("Chiudi")}})
}
