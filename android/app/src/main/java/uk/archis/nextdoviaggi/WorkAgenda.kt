package uk.archis.nextdoviaggi

import androidx.compose.foundation.background
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

internal data class WorkItem(val id:Long,val title:String,val kind:String,val priority:String,val status:String,val day:String,val instant:String,val overdue:Boolean) {
    val urgent get()=priority=="high"||priority=="critical"
    val timeLabel get()=if(day.isBlank())"Data da definire" else day+(if(instant.isNotBlank())" · "+instant.drop(11).take(5) else if(kind=="appointment")" · orario da definire" else "")
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
                items.add(WorkItem(t.getLong("id"),t.str("title"),t.str("kind"),t.str("priority"),t.str("status"),t.str("day"),t.str("instant"),t.optBoolean("overdue")))
            }
            if(page.isNull("next_after"))break
            val next=page.getLong("next_after")
            require(next>after&&items.size<=20000){"Agenda troppo grande: sincronizzazione incompleta"}
            after=next
        }while(true)
        val p=first?:error("Agenda non disponibile")
        return WorkAgenda(items,p.str("today"),p.str("week_start"),p.str("timezone"),p.str("updated_at"),p.str("display_name"))
    }
    fun detail(token:String,id:Long)=api.obj("/work/agenda/"+id,token)
    fun revoke(token:String)=api.obj("/work/revoke",token,JSONObject())
}
private val Blue=Color(0xFF83B6FF)
private val SandWork=Color(0xFFFFD49A)
private val MutedWork=Color(0xFFADC1D2)
private val PanelWork=Color(0xFF172B3D)
private val RedWork=Color(0xFFFF9595)
private fun statusName(value:String)=when(value){"review"->"Da verificare";"todo"->"Da fare";"doing"->"In corso";"waiting"->"In attesa";"done"->"Completata";else->value}
private fun priorityName(value:String)=when(value){"critical"->"Critica";"high"->"Alta";"low"->"Bassa";else->"Normale"}
@Composable
private fun WorkCard(title:String,body:@Composable ColumnScope.()->Unit){
    Card(Modifier.fillMaxWidth(),shape=RoundedCornerShape(20.dp),colors=CardDefaults.cardColors(containerColor=PanelWork)){
        Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){
            Text(title,color=Blue,fontWeight=FontWeight.Bold,fontSize=18.sp)
            body()
        }
    }
}
@Composable
internal fun WorkScreen(connected:Boolean,agenda:WorkAgenda?,busy:Boolean,error:String,defaultUrl:String,onPair:(String,String)->Unit,onRefresh:()->Unit,onDetail:(Long)->Unit,onDisconnect:()->Unit){
    var url by remember(defaultUrl){mutableStateOf(defaultUrl)}
    var code by remember{mutableStateOf("")}
    var confirm by remember{mutableStateOf(false)}
    var filter by remember{mutableStateOf("week")}
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
    Text("Aggiornata: "+agenda.updated.take(16).replace('T',' '),color=MutedWork,fontSize=12.sp)
    val monday=LocalDate.parse(agenda.weekStart).plusWeeks(offset.toLong())
    val sunday=monday.plusDays(6)
    val items=agenda.items
    fun inWeek(t:WorkItem)=t.day.isNotBlank()&&t.day>=monday.toString()&&t.day<=sunday.toString()
    WorkCard("Settimana"){
        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.SpaceBetween){
            TextButton(onClick={offset--;chosen="";filter="week"}){Text("‹")}
            Text(monday.format(DateTimeFormatter.ofPattern("dd/MM"))+" – "+sunday.format(DateTimeFormatter.ofPattern("dd/MM/yyyy")),fontSize=13.sp)
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
    val label=when(filter){"urgent"->"Urgenti";"review"->"Da verificare";"late"->"Scadute";"past"->"Appuntamenti trascorsi";"all"->"Tutte le voci aperte";"undated"->"Senza data";else->chosen.ifBlank{"Scadenze e appuntamenti della settimana"}}
    val shown=items.filter{t->when(filter){"urgent"->t.urgent;"review"->t.status=="review";"late"->t.overdue&&t.kind=="task";"past"->t.overdue&&t.kind=="appointment";"all"->true;"undated"->t.day.isBlank();else->inWeek(t)&&(chosen.isBlank()||t.day==chosen)}}.sortedWith(compareBy<WorkItem>{it.day.ifBlank{"9999"}}.thenBy{it.instant}.thenBy{it.id})
    Text(label+" · "+shown.size,fontSize=18.sp,fontWeight=FontWeight.Bold)
    if(shown.isEmpty())Text("Nessuna voce in questo filtro.",color=MutedWork)
    for(t in shown.take(visible)){
        WorkCard(t.title){
            Text((if(t.kind=="appointment")"Appuntamento" else "Scadenza")+" · "+t.timeLabel,color=MutedWork,fontSize=13.sp)
            Text(statusName(t.status)+" · Priorità "+priorityName(t.priority)+(if(t.overdue)if(t.kind=="task")" · Scaduta" else " · Trascorso" else ""),color=if(t.overdue)RedWork else if(t.urgent||t.status=="review")SandWork else Blue,fontSize=12.sp)
            TextButton(onClick={onDetail(t.id)},enabled=!busy){Text("Apri dettaglio")}
        }
    }
    if(visible<shown.size)OutlinedButton(onClick={visible+=50}){Text("Mostra altre voci")}
    Text("Sola lettura. Modifiche e notifiche saranno abilitate in una fase successiva.",color=MutedWork,fontSize=12.sp)
}
@Composable
internal fun WorkDetailDialog(detail:JSONObject,close:()->Unit){
    AlertDialog(onDismissRequest=close,title={Text(detail.str("title"))},text={
        Column(Modifier.heightIn(max=420.dp).verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(8.dp)){
            Text(statusName(detail.str("status"))+" · "+priorityName(detail.str("priority")))
            Text(detail.str("due_at").ifBlank{"Data da definire"},color=MutedWork)
            Text(detail.str("description").take(12000).ifBlank{"Nessuna descrizione"})
            if(detail.str("description").length>12000)Text("Descrizione lunga: consulta il testo completo sul web.",fontSize=12.sp)
        }
    },confirmButton={TextButton(onClick=close){Text("Chiudi")}})
}
