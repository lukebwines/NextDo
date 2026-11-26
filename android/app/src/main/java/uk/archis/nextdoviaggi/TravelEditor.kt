package uk.archis.nextdoviaggi

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import org.json.JSONArray
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import java.time.LocalDate
import java.time.temporal.ChronoUnit

data class TravelEditor(val kind:String,val tripId:String="",val revision:Int=-1,val initial:JSONObject=JSONObject(),val target:JSONObject=JSONObject(),val templates:List<BookingTemplate> = emptyList(),val choices:Map<String,List<Pair<String,String>>> = emptyMap())

@Composable
fun TravelEditDialog(editor:TravelEditor,busy:Boolean,error:String,onCancel:()->Unit,onSave:(JSONObject)->Unit) {
    val dynamic=editor.kind=="booking"&&editor.templates.isNotEmpty()
    val initial=remember(editor){bookingModel(editor.initial,editor.templates)}
    val existing=editor.target.has("id")
    var selected by remember(editor){mutableStateOf(initial.id)}
    var picking by remember(editor){mutableStateOf(false)}
    val specific=remember(editor){mutableStateListOf<BookingField>().apply{addAll(bookingFields(editor.initial))}}
    val models=editor.templates.let{if(it.any{t->t.id==initial.id})it else it+initial}
    val model=models.firstOrNull{it.id==selected}?:initial
    fun suggest(t:BookingTemplate){missingTemplateFields(specific.map{it.label},t.fields).take((200-specific.size).coerceAtLeast(0)).forEach{specific.add(BookingField(it,"",false,true))}}
    LaunchedEffect(editor){if(dynamic&&!existing)suggest(model)}
    val labels=when(editor.kind) {
        "new" -> listOf("title" to "Titolo", "subtitle" to "Sottotitolo", "start" to "Inizio", "end" to "Fine")
        "trip" -> listOf("title" to "Titolo","subtitle" to "Sottotitolo")
        "day" -> listOf("place" to "Località","headline" to "Titolo giornata","description" to "Descrizione")
        "event" -> listOf("time" to "Orario","title" to "Titolo","details" to "Dettagli")
        "budget" -> listOf("amount" to "Budget complessivo","currency" to "Valuta ISO")
        "expense" -> listOf("title" to "Descrizione","date" to "Data","amount" to "Importo originale","currency" to "Valuta ISO","status" to "Stato","category" to "Categoria","base_amount" to "Controvalore manuale (facoltativo)","base_currency" to "Valuta del controvalore","booking_id" to "Prenotazione","doc" to "Ricevuta in archivio","notes" to "Note")
        else -> listOf("title" to "Titolo","type" to "Tipologia","date" to "Data / periodo","place" to "Località","status" to "Stato","ref" to "Riferimento","price" to "Prezzo")
    }
    val values=remember(editor) { mutableStateMapOf<String,String>().apply { labels.forEach { (k,_) -> put(k,editor.initial.str(k).ifBlank{if(editor.kind=="new"&&(k=="start"||k=="end"))LocalDate.now().toString() else ""}) } } }
    val datesOk=if(editor.kind!="new") true else try {
        ChronoUnit.DAYS.between(LocalDate.parse(values["start"].orEmpty()),LocalDate.parse(values["end"].orEmpty())) in 0L..179L
    } catch(_:Exception) { false }
    val titleOk=editor.kind=="day" || editor.kind=="budget" || !values["title"].isNullOrBlank()
    AlertDialog(onDismissRequest={if(!busy)onCancel()},title={Text(when(editor.kind) {
        "new" -> "Nuovo viaggio"; "trip" -> "Dati viaggio"; "day" -> "Modifica giornata"; "event" -> "Evento"; "budget" -> "Budget"; "expense" -> "Spesa / ricevuta"; else -> "Prenotazione"
    })},text={
        Column(Modifier.heightIn(max=460.dp).verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(8.dp)) {
            if(dynamic){
                OutlinedButton(onClick={picking=true},enabled=!busy,modifier=Modifier.fillMaxWidth()){
                    Icon(bookingIcon(model.icon),null);Spacer(Modifier.width(8.dp));Text("Tipologia: "+model.label)
                }
                if(picking)AlertDialog(onDismissRequest={picking=false},title={Text("Tipologia di prenotazione")},text={
                    Column(Modifier.heightIn(max=360.dp).verticalScroll(rememberScrollState())){
                        for(t in models)TextButton(onClick={selected=t.id;picking=false;if(!existing){specific.removeAll{it.suggested&&it.value.isBlank()};suggest(t)}},modifier=Modifier.fillMaxWidth()){
                            Icon(bookingIcon(t.icon),null);Spacer(Modifier.width(8.dp));Text(t.label,Modifier.weight(1f))
                        }
                    }
                },confirmButton={TextButton(onClick={picking=false}){Text("Chiudi")}})
                if(model.roles.isNotEmpty())Text("Ruoli dei luoghi: "+model.roles.joinToString(" · "),style=MaterialTheme.typography.bodySmall)
            }
            for((k,label) in labels) {
                val value=values[k].orEmpty()
                when {
                    k=="start"||k=="end" -> DateField(label,value,{values[k]=it},enabled=!busy)
                    k=="time" -> TravelTimeInput(value,{values[k]=it},!busy)
                    k=="date"&&editor.kind=="expense" -> DateField(label,value,{values[k]=it},enabled=!busy,clearable=true)
                    k=="date" -> BookingDateInput(value,{values[k]=it},!busy)
                    editor.choices.containsKey(k) -> {
                        var expanded by remember(editor,k){mutableStateOf(false)}
                        val options=editor.choices[k].orEmpty()
                        Box {
                            OutlinedButton(onClick={expanded=true},enabled=!busy,modifier=Modifier.fillMaxWidth()){Text(label+": "+(options.firstOrNull{it.first==value}?.second?:value))}
                            DropdownMenu(expanded=expanded,onDismissRequest={expanded=false}){
                                options.forEach{(key,name)->DropdownMenuItem(text={Text(name)},onClick={values[k]=key;expanded=false})}
                            }
                        }
                    }
                    else -> OutlinedTextField(value,{values[k]=it.take(20000)},label={Text(if(k=="type"&&dynamic)"Categoria originale (facoltativa)" else label)},enabled=!busy,
                        singleLine=k!="details"&&k!="description",modifier=Modifier.fillMaxWidth())
                }
            }
            if(dynamic){
                Text("Campi specifici e personalizzati",style=MaterialTheme.typography.titleMedium)
                Text("I dati storici restano invariati. Aggiungi i campi del modello solo quando servono.",style=MaterialTheme.typography.bodySmall)
                for(i in specific.indices){
                    val entry=specific[i]
                    OutlinedTextField(entry.label,{specific[i]=specific[i].copy(label=it.take(20000))},label={Text("Nome campo")},enabled=!busy,modifier=Modifier.fillMaxWidth())
                    OutlinedTextField(entry.value,{specific[i]=specific[i].copy(value=it.take(20000))},label={Text("Valore")},enabled=!busy,modifier=Modifier.fillMaxWidth())
                    TextButton(onClick={specific.removeAt(i)},enabled=!busy){Text("Rimuovi campo")}
                }
                Row(horizontalArrangement=Arrangement.spacedBy(4.dp)){
                    TextButton(onClick={if(specific.size<200)specific.add(BookingField("","",false))},enabled=!busy){Text("+ Campo libero")}
                    TextButton(onClick={suggest(model)},enabled=!busy){Text("Aggiungi campi del modello")}
                }
            }
            if(!datesOk) Text("Inserisci date valide, periodo massimo 180 giorni.")
            if(error.isNotBlank()) Text(error,color=MaterialTheme.colorScheme.error)
            if(busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        }
    },confirmButton={TextButton(onClick={
        val b=JSONObject();labels.forEach{(k,_)->b.put(k,values[k].orEmpty())}
        if(dynamic){
            if(!existing||selected!=initial.id){b.put("_template_id",selected);if(b.str("type").isBlank())b.put("type",model.label)}
            val kept=retainedBookingFields(specific)
            if(!existing||editor.initial.has("fields")||kept.isNotEmpty())b.put("_specific_fields",JSONArray().apply{kept.forEach{put(JSONArray().put(it.label).put(it.value))}})
            if(existing&&selected==initial.id&&!editor.initial.has("type")&&b.str("type").isBlank())b.remove("type")
        }
        onSave(b)
    },enabled=!busy&&datesOk&&titleOk&&(!dynamic||specific.size<=200&&retainedBookingFields(specific).all{row->row.label.isNotBlank()||bookingFields(editor.initial).any{it.label==row.label&&it.value==row.value}})){Text("Salva")}},
      dismissButton={TextButton(onClick=onCancel,enabled=!busy){Text("Annulla")}})
}

/** Text fallback is intentional for inherited bookings, ranges and local-time annotations. */
@Composable
private fun TravelTimeInput(value:String,change:(String)->Unit,enabled:Boolean){
    var freeText by remember{mutableStateOf(false)}
    TimeField("Orario locale",value,change,enabled=enabled)
    if(value.isNotBlank()&&ItalianDateTime.parseTime(value)==null)Text("L’orario originale contiene indicazioni complesse. La scelta di un’ora lo sostituisce; puoi conservarlo come testo libero.",style=MaterialTheme.typography.bodySmall)
    TextButton(onClick={freeText=!freeText},enabled=enabled){Text(if(freeText)"Nascondi testo libero" else "Orario complesso / testo libero")}
    if(freeText)OutlinedTextField(value,{change(it.take(20000))},label={Text("Orario originale / intervallo")},enabled=enabled,modifier=Modifier.fillMaxWidth())
}
@Composable
private fun BookingDateInput(value:String,change:(String)->Unit,enabled:Boolean){
    var freeText by remember{mutableStateOf(false)}
    val first=ItalianDateTime.firstDate(value)
    val period=ItalianDateTime.period(value)
    val end=period?.second?.toString().orEmpty()
    DateField("Data / periodo",value,{start->
        val selected=ItalianDateTime.parseDate(start)
        change(if(selected!=null&&period!=null&&selected<=period.second)start+" — "+period.second.toString() else start)
    },enabled=enabled,clearable=true)
    if(first!=null){
        DateField("Fine periodo (facoltativa)",end,{last->
            change(if(last.isBlank())first.toString() else first.toString()+" — "+last)
        },enabled=enabled,clearable=true,fallback=first,min=first)
    }
    Text("La scelta di una data sostituisce il valore precedente. Per indicazioni complesse o con fusi diversi conserva il testo originale.",style=MaterialTheme.typography.bodySmall)
    TextButton(onClick={freeText=!freeText},enabled=enabled){Text(if(freeText)"Nascondi testo libero" else "Periodo complesso / testo libero")}
    if(freeText)OutlinedTextField(value,{change(it.take(20000))},label={Text("Data / periodo originale")},enabled=enabled,modifier=Modifier.fillMaxWidth())
}
