package uk.archis.nextdoviaggi

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
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
    val timeLabel get()=if(day.isBlank())"Data da definire" else day+(if(instant.isNotBlank())" · "+instant.drop(11).take(5) else if(kind=="appointment")" · orario da definire" else "")
}
internal data class CompletionSummary(val period:String,val count:Int)
internal fun completionLabel(period:String)=if(period=="year")"anno corrente" else "$period giorni"
internal data class WorkAgenda(val items:List<WorkItem>,val today:String,val weekStart:String,val timezone:String,val updated:String,val name:String,val completion:CompletionSummary?=null)
internal data class CompletedPage(val items:List<WorkItem>,val next:Long?,val period:String,val total:Int)
internal class WorkApi(private val base:String){
    private val api=TravelApi(base)
    fun pair(code:String):JSONObject {
        val result=api.obj("/work/pair",data=JSONObject().put("code",code.trim()).put("label","Android "+android.os.Build.MODEL.take(60)))
        return JSONObject().put("url",base.trim()).put("token",result.getString("device_token"))
    }
    private fun parseItem(t:JSONObject)=WorkItem(t.getLong("id"),t.str("title"),t.str("kind"),t.str("priority"),t.str("status"),t.str("day"),t.str("instant"),t.optBoolean("overdue"),t.str("revision"),t.optBoolean("acknowledged"))
    fun completed(token:String,after:Long=0):CompletedPage {
        val page=api.obj("/work/completed?after="+after,token)
        return CompletedPage(page.arr("items").map(::parseItem),if(page.isNull("next_after"))null else page.getLong("next_after"),page.str("period"),page.optInt("total"))
    }
    fun agenda(token:String):WorkAgenda {
        val items=mutableListOf<WorkItem>();var after=0L;var first:JSONObject?=null
        do {
            val page=api.obj("/work/agenda?after="+after,token)
            if(first==null)first=page
            for(t in page.arr("items")){
                items.add(parseItem(t))
            }
            if(page.isNull("next_after"))break
            val next=page.getLong("next_after")
            require(next>after&&items.size<=20000){"Agenda troppo grande: sincronizzazione incompleta"}
            after=next
        }while(true)
        val p=first?:error("Agenda non disponibile")
        val summary=p.optJSONObject("completion_summary")?.let{CompletionSummary(it.str("period"),it.optInt("count"))}
        return WorkAgenda(items,p.str("today"),p.str("week_start"),p.str("timezone"),p.str("updated_at"),p.str("display_name"),summary)
    }
    fun acknowledge(token:String,id:Long,revision:String)=api.obj("/work/agenda/"+id+"/ack",token,JSONObject().put("revision",revision))
    fun detail(token:String,id:Long)=api.obj("/work/agenda/"+id,token)
    fun revoke(token:String)=api.obj("/work/revoke",token,JSONObject())
}
private val Blue=Color(0xFF83B6FF)
private val SandWork=Color(0xFFFFD49A)
private val MutedWork=Color(0xFFADC1D2)
private val PanelWork=ShellPanel
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
    "overdue"->t.overdue
    else->if(filter.startsWith("day:"))t.day==filter.removePrefix("day:") else true
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
internal fun WorkScreen(connected:Boolean,agenda:WorkAgenda?,busy:Boolean,error:String,defaultUrl:String,onPair:(String,String)->Unit,onRefresh:()->Unit,onDetail:(Long)->Unit,onDisconnect:()->Unit,onAck:(Long,String)->Unit,initialFilter:String="all",completed:CompletedPage?=null,completedBusy:Boolean=false,completedError:String="",onLoadCompleted:(Long)->Unit={}){
    var url by remember(defaultUrl){mutableStateOf(defaultUrl)}
    var code by remember{mutableStateOf("")}
    var confirm by remember{mutableStateOf(false)}
    var filter by remember(initialFilter){mutableStateOf(initialFilter)}
    var chosen by remember{mutableStateOf("")}
    var offset by remember{mutableIntStateOf(0)}
    var visible by remember(filter,chosen,offset){mutableIntStateOf(50)}
    Text("Agenda professionale",fontSize=23.sp,fontWeight=FontWeight.ExtraBold)
    if(error.isNotBlank())Text(error,color=RedWork,fontSize=13.sp)
    if(busy)LinearProgressIndicator(Modifier.fillMaxWidth())
    if(!connected){
        WorkCard("Associazione dedicata"){
            Text("In NextDo Web, apri Impostazioni → App Android → Dispositivi e associazione e genera un codice monouso. L’associazione Viaggi non viene modificata.",color=MutedWork,fontSize=13.sp)
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
    Text("Aggiornata: "+agenda.updated.take(16).replace('T',' '),color=MutedWork,fontSize=12.sp)
    val today=LocalDate.parse(agenda.today)
    val monday=LocalDate.parse(agenda.weekStart).plusWeeks(offset.toLong())
    val sunday=monday.plusDays(6)
    val items=agenda.items
    fun inWeek(t:WorkItem)=t.day.isNotBlank()&&t.day>=monday.toString()&&t.day<=sunday.toString()
    if(filter=="completed"){
        TextButton(onClick={filter="all"}){Text("← Attività aperte")}
        CompletedWorkList(completed,completedBusy,completedError,onLoadCompleted,onDetail)
        return
    }
    val filterOptions=listOf(
        "all" to "Tutte","tasks" to "Scadenze","appointments" to "Appuntamenti",
        "urgent" to "Urgenti","review" to "Da verificare","todo" to "Da fare",
        "late" to "Scadute","past" to "Trascorsi","undated" to "Senza data")
    for(group in filterOptions.chunked(3)){
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(6.dp)){
            for((key,label) in group)FilterChip(selected=filter==key,onClick={filter=key;chosen=""},label={Text(label+" "+items.count{workMatches(it,key)},fontSize=12.sp)},enabled=!busy)
        }
    }
    if(filter=="calendar"){
        BentoCalendar(today,items.mapNotNull{it.day.takeIf(String::isNotBlank)}.toSet(),items.filter{it.status=="review"}.map{it.day}.toSet(),onDay={filter="day:"+it;chosen=""})
        TextButton(onClick={filter="week";offset=0;chosen=""}){Text("Agenda della settimana")}
        return
    }
    TextButton(onClick={filter="calendar";chosen=""}){Icon(Icons.Default.CalendarMonth,null);Spacer(Modifier.width(6.dp));Text("Calendario mensile")}
    agenda.completion?.let{TextButton(onClick={filter="completed";onLoadCompleted(0)},enabled=!busy){Text("Completate · "+completionLabel(it.period)+" ("+it.count+")")}}
    val label=when(filter){
        "tasks"->"Scadenze e attività";"appointments"->"Appuntamenti";"todo"->"Da fare";"urgent"->"Urgenti";"review"->"Da verificare";"late"->"Scadute";"past"->"Appuntamenti trascorsi";"all"->"Tutte le voci aperte";"undated"->"Senza data";"overdue"->"Scadute / trascorsi";"future"->"Prossimi impegni";"week"->"Agenda della settimana";else->if(filter.startsWith("day:"))shortDate(filter.removePrefix("day:")) else "Agenda"
    }
    val shown=orderedWork(items.filter{t->when(filter){"week"->inWeek(t)&&(chosen.isBlank()||t.day==chosen);"future"->t.day>today.plusDays(1).toString();else->workMatches(t,filter)}})
    Text(label+" · "+shown.size,fontSize=17.sp,fontWeight=FontWeight.Bold)
    if(shown.isEmpty())Text("Nessuna voce in questo filtro.",color=MutedWork)
    for(t in shown.take(visible))WorkItemRow(t,!busy,onDetail,onAck)
    if(visible<shown.size)OutlinedButton(onClick={visible+=50}){Text("Mostra altre voci")}
    BentoCalendar(today,items.mapNotNull{it.day.takeIf(String::isNotBlank)}.toSet(),items.filter{it.status=="review"}.map{it.day}.toSet(),filter.removePrefix("day:").takeIf{filter.startsWith("day:")}.orEmpty(),onDay={filter="day:"+it;chosen=""})
    WorkCard("Agenda settimanale"){
        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.SpaceBetween){
            TextButton(onClick={offset--;chosen="";filter="week"}){Text("‹")}
            Text(shortDate(monday.toString())+" – "+shortDate(sunday.toString()),fontSize=13.sp)
            TextButton(onClick={offset++;chosen="";filter="week"}){Text("›")}
        }
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(2.dp)){
            for(n in 0L..6L){
                val day=monday.plusDays(n);val ds=day.toString()
                TextButton(onClick={filter="day:"+ds;chosen=""},modifier=Modifier.weight(1f),contentPadding=PaddingValues(0.dp)){
                    Column(horizontalAlignment=Alignment.CenterHorizontally){
                        Text(day.format(DateTimeFormatter.ofPattern("EEE",Locale.ITALIAN)),fontSize=10.sp)
                        Text(day.dayOfMonth.toString(),fontWeight=FontWeight.Bold)
                        Text(items.count{it.day==ds}.toString(),fontSize=10.sp,color=MutedWork)
                    }
                }
            }
        }
        TextButton(onClick={offset=0;chosen="";filter="week"}){Text("Settimana corrente")}
    }
    Text("Presa visione sincronizzata; non modifica lo stato dell’attività.",color=MutedWork,fontSize=12.sp)
}
@Composable
internal fun WorkDetailDialog(detail:JSONObject,close:()->Unit){
    AlertDialog(onDismissRequest=close,title={Text(detail.str("title"))},text={
        Column(Modifier.heightIn(max=420.dp).verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(8.dp)){
            Text(statusName(detail.str("status"))+" · "+priorityName(detail.str("priority")))
            Text("Scadenza: "+detail.str("due_at").ifBlank{"Data da definire"},color=MutedWork)
            if(detail.str("completed_at").isNotBlank())Text("Completamento: "+detail.str("completed_at").replace("T"," ").removeSuffix("Z")+" UTC",color=MutedWork)
            Text(detail.str("description").take(12000).ifBlank{"Nessuna descrizione"})
            if(detail.str("description").length>12000)Text("Descrizione lunga: consulta il testo completo sul web.",fontSize=12.sp)
        }
    },confirmButton={TextButton(onClick=close){Text("Chiudi")}})
}

@Composable
private fun CompletedWorkList(data:CompletedPage?,busy:Boolean,error:String,load:(Long)->Unit,onDetail:(Long)->Unit){
    if(error.isNotBlank())Text(error,color=ShellSand,fontSize=12.sp)
    if(busy)LinearProgressIndicator(Modifier.fillMaxWidth())
    if(data==null){
        Text("Storico completate",fontWeight=FontWeight.Bold)
        TextButton(onClick={load(0)},enabled=!busy){Text("Carica completate")}
        return
    }
    Text("Completate · "+completionLabel(data.period)+" · "+data.total,fontWeight=FontWeight.Bold)
    if(data.items.isEmpty())Text("Nessuna attività completata nel periodo.",color=ShellMuted)
    for(t in data.items)WorkItemRow(t,!busy,onDetail)
    data.next?.let{next->OutlinedButton(onClick={load(next)},enabled=!busy){Text("Carica altre completate")}}
}
