package uk.archis.nextdoviaggi

import android.app.Activity
import android.app.DatePickerDialog
import android.app.TimePickerDialog
import android.content.Context
import android.content.ContextWrapper
import android.content.res.Configuration
import android.view.ContextThemeWrapper
import android.view.WindowManager
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CalendarToday
import androidx.compose.material.icons.filled.AccessTime
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.DialogWindowProvider
import java.time.LocalDate
import java.time.LocalTime
import java.util.Calendar
import java.util.Locale

internal data class PickerAppearance(val light:Boolean=false,val palette:String="ocean") {
    fun style():Int=when(palette){
        "forest"->if(light)R.style.NextDoPickerLightForest else R.style.NextDoPickerDarkForest
        "sunset"->if(light)R.style.NextDoPickerLightSunset else R.style.NextDoPickerDarkSunset
        "lavender"->if(light)R.style.NextDoPickerLightLavender else R.style.NextDoPickerDarkLavender
        else->if(light)R.style.NextDoPickerLightOcean else R.style.NextDoPickerDarkOcean
    }
}

private fun italianContext(context:Context,appearance:PickerAppearance):ContextThemeWrapper {
    val config=Configuration(context.resources.configuration)
    config.setLocale(Locale.ITALY)
    config.setLayoutDirection(Locale.ITALY)
    return ContextThemeWrapper(context,appearance.style()).apply{applyOverrideConfiguration(config)}
}
private tailrec fun activity(context:Context):Activity?=when(context){
    is Activity->context
    is ContextWrapper->if(context.baseContext===context)null else activity(context.baseContext)
    else->null
}
@Composable
private fun secureParent():Boolean {
    val context=LocalContext.current
    val parent=LocalView.current.parent as? DialogWindowProvider
    val flags=parent?.window?.attributes?.flags?:activity(context)?.window?.attributes?.flags?:0
    return flags and WindowManager.LayoutParams.FLAG_SECURE != 0
}

/** Calendar starts on today or existing date. Selecting/cancelling never changes an optional value implicitly. */
@Composable
internal fun DateField(label:String,value:String,onChange:(String)->Unit,enabled:Boolean=true,
                       clearable:Boolean=false,appearance:PickerAppearance=PickerAppearance(),
                       fallback:LocalDate=LocalDate.now(),min:LocalDate?=null,max:LocalDate?=null,
                       display:String=ItalianDateTime.temporalText(value)) {
    var open by remember{mutableStateOf(false)}
    val callback by rememberUpdatedState(onChange)
    val context=LocalContext.current
    val secure=secureParent()
    Column(Modifier.fillMaxWidth()){
        Text(label,style=MaterialTheme.typography.labelMedium)
        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
            OutlinedButton(onClick={open=true},enabled=enabled,modifier=Modifier.weight(1f)){
                Icon(Icons.Default.CalendarToday,contentDescription=null)
                Spacer(Modifier.width(8.dp))
                Text(display.ifBlank{"Seleziona data"},modifier=Modifier.weight(1f))
            }
            if(clearable&&value.isNotBlank())IconButton(onClick={onChange("")},enabled=enabled){Icon(Icons.Default.Close,"Rimuovi "+label.lowercase(Locale.ITALY))}
        }
    }
    if(open)DisposableEffect(context,appearance){
        var initial=ItalianDateTime.firstDate(value)?:fallback
        if(min!=null&&initial<min)initial=min
        if(max!=null&&initial>max)initial=max
        val dialog=DatePickerDialog(italianContext(context,appearance),appearance.style(),
            {_,y,m,d->callback(LocalDate.of(y,m+1,d).toString())},initial.year,initial.monthValue-1,initial.dayOfMonth)
        dialog.datePicker.firstDayOfWeek=Calendar.MONDAY
        fun millis(d:LocalDate):Long=Calendar.getInstance().apply{clear();set(d.year,d.monthValue-1,d.dayOfMonth,12,0,0)}.timeInMillis
        min?.let{dialog.datePicker.minDate=millis(it)}
        max?.let{dialog.datePicker.maxDate=millis(it)}
        dialog.setOnDismissListener{open=false}
        dialog.show()
        if(secure)dialog.window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        onDispose{dialog.setOnDismissListener(null);dialog.dismiss()}
    }
}

/** Native 24-hour picker; no default value is committed until explicitly confirmed. */
@Composable
internal fun TimeField(label:String,value:String,onChange:(String)->Unit,enabled:Boolean=true,
                       clearable:Boolean=true,appearance:PickerAppearance=PickerAppearance()) {
    var open by remember{mutableStateOf(false)}
    val callback by rememberUpdatedState(onChange)
    val context=LocalContext.current
    val secure=secureParent()
    Column(Modifier.fillMaxWidth()){
        Text(label,style=MaterialTheme.typography.labelMedium)
        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
            OutlinedButton(onClick={open=true},enabled=enabled,modifier=Modifier.weight(1f)){
                Icon(Icons.Default.AccessTime,contentDescription=null)
                Spacer(Modifier.width(8.dp))
                Text(ItalianDateTime.temporalText(value).ifBlank{"Seleziona ora"},modifier=Modifier.weight(1f))
            }
            if(clearable&&value.isNotBlank())IconButton(onClick={onChange("")},enabled=enabled){Icon(Icons.Default.Close,"Rimuovi orario")}
        }
    }
    if(open)DisposableEffect(context,appearance){
        val initial=ItalianDateTime.parseTime(value)?:LocalTime.now()
        val dialog=TimePickerDialog(italianContext(context,appearance),appearance.style(),
            {_,h,m->callback(ItalianDateTime.time(LocalTime.of(h,m)))},initial.hour,initial.minute,true)
        dialog.setOnDismissListener{open=false}
        dialog.show()
        if(secure)dialog.window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        onDispose{dialog.setOnDismissListener(null);dialog.dismiss()}
    }
}
