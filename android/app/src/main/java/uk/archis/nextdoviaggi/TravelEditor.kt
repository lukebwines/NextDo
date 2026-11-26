package uk.archis.nextdoviaggi

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import java.time.LocalDate
import java.time.temporal.ChronoUnit

data class TravelEditor(val kind:String,val tripId:String="",val revision:Int=-1,val initial:JSONObject=JSONObject(),val target:JSONObject=JSONObject())

@Composable
fun TravelEditDialog(editor:TravelEditor,busy:Boolean,error:String,onCancel:()->Unit,onSave:(JSONObject)->Unit) {
    val labels=when(editor.kind) {
        "new" -> listOf("title" to "Titolo", "subtitle" to "Sottotitolo", "start" to "Inizio", "end" to "Fine")
        "trip" -> listOf("title" to "Titolo","subtitle" to "Sottotitolo")
        "day" -> listOf("place" to "Località","headline" to "Titolo giornata","description" to "Descrizione")
        "event" -> listOf("time" to "Orario","title" to "Titolo","details" to "Dettagli")
        else -> listOf("title" to "Titolo","type" to "Tipologia","date" to "Data / periodo","place" to "Località","status" to "Stato","ref" to "Riferimento","price" to "Prezzo")
    }
    val values=remember(editor) { mutableStateMapOf<String,String>().apply { labels.forEach { (k,_) -> put(k,editor.initial.str(k).ifBlank{if(editor.kind=="new"&&(k=="start"||k=="end"))LocalDate.now().toString() else ""}) } } }
    val datesOk=if(editor.kind!="new") true else try {
        ChronoUnit.DAYS.between(LocalDate.parse(values["start"].orEmpty()),LocalDate.parse(values["end"].orEmpty())) in 0L..179L
    } catch(_:Exception) { false }
    val titleOk=editor.kind=="day" || !values["title"].isNullOrBlank()
    AlertDialog(onDismissRequest={if(!busy)onCancel()},title={Text(when(editor.kind) {
        "new" -> "Nuovo viaggio"; "trip" -> "Dati viaggio"; "day" -> "Modifica giornata"; "event" -> "Evento"; else -> "Prenotazione"
    })},text={
        Column(Modifier.heightIn(max=460.dp).verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(8.dp)) {
            for((k,label) in labels) {
                val value=values[k].orEmpty()
                when {
                    k=="start"||k=="end" -> DateField(label,value,{values[k]=it},enabled=!busy)
                    k=="time" -> TravelTimeInput(value,{values[k]=it},!busy)
                    k=="date" -> BookingDateInput(value,{values[k]=it},!busy)
                    else -> OutlinedTextField(value,{values[k]=it.take(20000)},label={Text(label)},enabled=!busy,
                        singleLine=k!="details"&&k!="description",modifier=Modifier.fillMaxWidth())
                }
            }
            if(!datesOk) Text("Inserisci date valide, periodo massimo 180 giorni.")
            if(error.isNotBlank()) Text(error,color=MaterialTheme.colorScheme.error)
            if(busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        }
    },confirmButton={TextButton(onClick={val b=JSONObject();labels.forEach{(k,_)->b.put(k,values[k].orEmpty())};onSave(b)},enabled=!busy&&datesOk&&titleOk){Text("Salva")}},
      dismissButton={TextButton(onClick=onCancel,enabled=!busy){Text("Annulla")}})
}

/** Text fallback is intentional for inherited bookings, ranges and local-time annotations. */
@Composable
private fun TravelTimeInput(value:String,change:(String)->Unit,enabled:Boolean){
    var freeText by remember{mutableStateOf(false)}
    TimeField("Orario locale",value,change,enabled=enabled)
    TextButton(onClick={freeText=!freeText},enabled=enabled){Text(if(freeText)"Nascondi testo libero" else "Orario complesso / testo libero")}
    if(freeText)OutlinedTextField(value,{change(it.take(20000))},label={Text("Orario originale / intervallo")},enabled=enabled,modifier=Modifier.fillMaxWidth())
}
@Composable
private fun BookingDateInput(value:String,change:(String)->Unit,enabled:Boolean){
    var freeText by remember{mutableStateOf(false)}
    val first=ItalianDateTime.firstDate(value)
    val canonical=Regex("""(\d{4}-\d{2}-\d{2}) — (\d{4}-\d{2}-\d{2})""").matchEntire(value)
    val end=canonical?.groupValues?.get(2).orEmpty()
    DateField("Data / periodo",value,change,enabled=enabled,clearable=true)
    if(first!=null){
        DateField("Fine periodo (facoltativa)",end,{last->
            change(if(last.isBlank())first.toString() else first.toString()+" — "+last)
        },enabled=enabled,clearable=true,fallback=first,min=first)
    }
    Text("La scelta di una data sostituisce il valore precedente. Per indicazioni complesse o con fusi diversi conserva il testo originale.",style=MaterialTheme.typography.bodySmall)
    TextButton(onClick={freeText=!freeText},enabled=enabled){Text(if(freeText)"Nascondi testo libero" else "Periodo complesso / testo libero")}
    if(freeText)OutlinedTextField(value,{change(it.take(20000))},label={Text("Data / periodo originale")},enabled=enabled,modifier=Modifier.fillMaxWidth())
}
