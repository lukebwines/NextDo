package uk.archis.nextdoviaggi

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.ui.graphics.vector.ImageVector
import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale

data class BookingTemplate(val id:String,val label:String,val icon:String,val fields:List<String>,val roles:List<String>)

private fun JSONArray.strings()=(0 until length()).map{getString(it)}
internal fun bookingCatalog(a:JSONArray?):List<BookingTemplate>{
    if(a==null)return emptyList()
    require(a.length()<=60){"Catalogo tipologie non valido"}
    val models=(0 until a.length()).map{i->
        val t=a.getJSONObject(i)
        BookingTemplate(t.getString("id"),t.getString("label"),t.getString("icon"),t.getJSONArray("fields").strings(),t.getJSONArray("roles").strings())
    }
    require(models.map{it.id}.distinct().size==models.size&&models.all{it.id.isNotBlank()&&it.label.isNotBlank()&&it.fields.size<=40&&it.roles.size<=12}){"Catalogo tipologie non valido"}
    return models
}
internal fun inferBookingKind(explicit:String,type:String,catalog:List<BookingTemplate>):String{
    if(explicit.isNotBlank())return explicit
    val v=type.trim().lowercase(Locale.ROOT)
    catalog.firstOrNull{it.id!="other"&&it.label.lowercase(Locale.ROOT)==v}?.let{return it.id}
    return when{
        Regex("assicurazion|polizza|insurance").containsMatchIn(v)->"insurance"
        Regex("parcheggio|parking").containsMatchIn(v)->"parking"
        Regex("esim|e-sim|connettivit").containsMatchIn(v)->"esim"
        Regex("vol[io]|flight|aere").containsMatchIn(v)->"flight"
        Regex("hotel|alloggio|accommodation|albergo").containsMatchIn(v)->"hotel"
        Regex("auto|car rental|noleggio").containsMatchIn(v)->"car"
        Regex("tren[oi]|train").containsMatchIn(v)->"train"
        Regex("attrazion|bigliett|attraction").containsMatchIn(v)->"attraction"
        Regex("ristorant|restaurant").containsMatchIn(v)->"restaurant"
        else->"other"
    }
}
internal fun bookingModel(b:JSONObject,catalog:List<BookingTemplate>):BookingTemplate{
    val id=inferBookingKind(b.str("kind"),b.str("type"),catalog)
    catalog.firstOrNull{it.id==id}?.let{return it}
    val fallback=mapOf("flight" to "plane","hotel" to "hotel","car" to "car","train" to "train","attraction" to "ticket","restaurant" to "restaurant","insurance" to "shield","parking" to "parking","esim" to "phone")
    return BookingTemplate(id,b.str("template_label").ifBlank{b.str("type").ifBlank{if(id=="other")"Altro" else id}},b.str("template_icon").ifBlank{fallback[id]?:"folder"},emptyList(),emptyList())
}
internal fun bookingIcon(name:String):ImageVector=when(name){
    "plane"->Icons.Default.Flight
    "hotel"->Icons.Default.Hotel
    "car"->Icons.Default.DirectionsCar
    "train"->Icons.Default.Train
    "ticket"->Icons.Default.ConfirmationNumber
    "restaurant"->Icons.Default.Restaurant
    "shield"->Icons.Default.Shield
    "parking"->Icons.Default.LocalParking
    "phone"->Icons.Default.Phone
    "calendar"->Icons.Default.CalendarToday
    "note"->Icons.Default.Note
    "bell"->Icons.Default.Notifications
    else->Icons.Default.Folder
}
internal fun missingTemplateFields(existing:List<String>,suggested:List<String>):List<String>{
    val known=existing.map{it.trim().lowercase(Locale.ROOT)}.toMutableSet()
    return suggested.filter{known.add(it.trim().lowercase(Locale.ROOT))}
}
internal data class BookingField(val label:String,val value:String,val original:Boolean=true)
internal fun bookingFields(b:JSONObject):List<BookingField>{
    val rows=b.optJSONArray("fields")?:return emptyList()
    return (0 until rows.length()).mapNotNull{rows.optJSONArray(it)?.let{a->BookingField(a.optString(0),a.optString(1))}}
}
