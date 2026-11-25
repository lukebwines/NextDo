package uk.archis.nextdoviaggi

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Environment
import android.provider.MediaStore
import androidx.core.content.FileProvider
import java.io.File
import java.util.UUID

internal object PdfExport {
    internal fun safeName(raw:String):String {
        val name=raw.replace(Regex("[\\\\/\\p{Cntrl}]"),"_").trim().trim('.').take(100)
        val base=name.removeSuffix(".pdf").removeSuffix(".PDF").ifBlank{"documento"}
        return base+".pdf"
    }
    fun download(context:Context,name:String,bytes:ByteArray):Uri {
        val resolver=context.contentResolver
        val values=ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME,safeName(name))
            put(MediaStore.MediaColumns.MIME_TYPE,"application/pdf")
            put(MediaStore.MediaColumns.RELATIVE_PATH,Environment.DIRECTORY_DOWNLOADS+"/NextDo")
            put(MediaStore.MediaColumns.IS_PENDING,1)
        }
        val uri=resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,values)?:error("Impossibile creare il file")
        try{
            resolver.openOutputStream(uri,"w")?.use{it.write(bytes)}?:error("Impossibile scrivere il PDF")
            val ready=ContentValues().apply{put(MediaStore.MediaColumns.IS_PENDING,0)}
            check(resolver.update(uri,ready,null,null)>0){"Salvataggio non riuscito"}
            return uri
        }catch(e:Exception){runCatching{resolver.delete(uri,null,null)};throw e}
    }
    fun externalCopy(context:Context,name:String,bytes:ByteArray):Uri {
        val directory=File(context.cacheDir,"pdf-exports/"+UUID.randomUUID())
        check(directory.mkdirs()){"Impossibile preparare il PDF"}
        try {
            val file=File(directory,safeName(name));file.writeBytes(bytes)
            return FileProvider.getUriForFile(context,context.packageName+".updates",file)
        }catch(e:Exception){directory.deleteRecursively();throw e}
    }
    fun cleanup(context:Context){
        val cutoff=System.currentTimeMillis()-24*60*60*1000L
        File(context.cacheDir,"pdf-exports").listFiles()?.filter{it.lastModified()<cutoff}?.forEach{it.deleteRecursively()}
    }
}
