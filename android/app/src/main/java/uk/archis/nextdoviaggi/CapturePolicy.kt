package uk.archis.nextdoviaggi
internal fun captureAllowed(foreground:Boolean,locked:Boolean,sdk:Int,area:NextDoArea,work:Boolean,personal:Boolean):Boolean {
    if(!foreground||locked||sdk<33)return false
    return when(area){NextDoArea.HOME,NextDoArea.WORK->work;NextDoArea.PERSONAL,NextDoArea.TRIPS->personal;NextDoArea.SETTINGS->false}
}
