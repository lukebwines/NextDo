package uk.archis.nextdoviaggi

import android.graphics.Bitmap
import android.view.Window
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.pager.VerticalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.math.min
import kotlin.math.max

internal fun pdfZoom(value:Float):Float = value.coerceIn(1f,5f)
internal fun pdfPan(offset:Float,content:Float,viewport:Float,scale:Float):Float {
    val bound=max(0f,(content*scale-viewport)/2f)
    return offset.coerceIn(-bound,bound)
}

@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
internal fun NextDoPdfViewer(
    window:Window,name:String,count:Int,firstPage:Bitmap?,render:(Int)->Bitmap,
    busy:Boolean,message:String,error:String,onClose:()->Unit,onExport:(String)->Unit,onDismissMessage:()->Unit
) {
    val pager=rememberPagerState(pageCount={count})
    val scope=rememberCoroutineScope()
    var zoom by remember { mutableFloatStateOf(1f) }
    var rotation by remember { mutableIntStateOf(0) }
    var offset by remember { mutableStateOf(Offset.Zero) }
    var immersive by remember { mutableStateOf(false) }
    var confirm by remember { mutableStateOf("") }
    var menu by remember { mutableStateOf(false) }
    val background=Color(0xFF08121D)
    fun resetZoom(){zoom=1f;offset=Offset.Zero}
    fun go(delta:Int) {
        val target=(pager.currentPage+delta).coerceIn(0,(count-1).coerceAtLeast(0))
        resetZoom()
        scope.launch { pager.animateScrollToPage(target) }
    }
    LaunchedEffect(pager.currentPage){resetZoom()}
    DisposableEffect(immersive) {
        val controller=WindowCompat.getInsetsController(window,window.decorView)
        if(immersive){
            controller.systemBarsBehavior=WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            controller.hide(WindowInsetsCompat.Type.systemBars())
        }
        onDispose { controller.show(WindowInsetsCompat.Type.systemBars()) }
    }
    if(confirm.isNotEmpty()) {
        val action=confirm
        AlertDialog(onDismissRequest={confirm=""},title={Text(when(action){"download"->"Scaricare il PDF?";"share"->"Condividere il PDF?";else->"Aprire con un'altra app?"})},
            text={Text(if(action=="download")"Il documento verrà salvato in Download/NextDo, fuori dalla protezione di NextDo." else "L'app scelta potrà leggere o conservare una copia del documento al di fuori di NextDo. Procedere solo se desiderato.")},
            confirmButton={TextButton(onClick={confirm="";onExport(action)},enabled=!busy){Text("Continua")}},
            dismissButton={TextButton(onClick={confirm=""}){Text("Annulla")}})
    }
    Box(Modifier.fillMaxSize().background(background).safeDrawingPadding()){
        Column(Modifier.fillMaxSize()){
            if(!immersive){
                Row(Modifier.fillMaxWidth().padding(horizontal=4.dp,vertical=3.dp),verticalAlignment=Alignment.CenterVertically){
                    IconButton(onClick=onClose,enabled=!busy){Icon(Icons.Default.ArrowBack,"Torna al viaggio")}
                    Column(Modifier.weight(1f)){
                        Text(name,maxLines=1,overflow=TextOverflow.Ellipsis,fontSize=15.sp)
                        Text("Documento PDF",fontSize=11.sp,color=MaterialTheme.colorScheme.primary)
                    }
                    IconButton(onClick={confirm="download"},enabled=!busy){Icon(Icons.Default.Download,"Scarica PDF")}
                    Box {
                        IconButton(onClick={menu=true},enabled=!busy){Icon(Icons.Default.MoreVert,"Altre azioni PDF")}
                        DropdownMenu(expanded=menu,onDismissRequest={menu=false}){
                            DropdownMenuItem(text={Text("Apri con altra app")},onClick={menu=false;confirm="open"},leadingIcon={Icon(Icons.Default.OpenInNew,null)})
                            DropdownMenuItem(text={Text("Condividi PDF")},onClick={menu=false;confirm="share"},leadingIcon={Icon(Icons.Default.Share,null)})
                        }
                    }
                    IconButton(onClick={immersive=true},enabled=!busy){Icon(Icons.Default.Fullscreen,"Schermo intero")}
                }
                if(busy)LinearProgressIndicator(Modifier.fillMaxWidth())
                if(message.isNotBlank()||error.isNotBlank())Row(Modifier.fillMaxWidth().padding(horizontal=10.dp),verticalAlignment=Alignment.CenterVertically){
                    Text(error.ifBlank{message},Modifier.weight(1f),fontSize=12.sp,color=if(error.isNotBlank())MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
                    TextButton(onClick=onDismissMessage){Text("Chiudi")}
                }
            }
            if(count>0)VerticalPager(state=pager,modifier=Modifier.weight(1f).fillMaxWidth(),
                userScrollEnabled=zoom<=1.01f,beyondViewportPageCount=0){index->
                var bitmap by remember(index){mutableStateOf(if(index==0)firstPage else null)}
                var failed by remember(index){mutableStateOf(false)}
                var retry by remember(index){mutableIntStateOf(0)}
                LaunchedEffect(index,retry){
                    if(bitmap==null){
                        try{bitmap=withContext(Dispatchers.IO){render(index)}}
                        catch(e:CancellationException){throw e}
                        catch(_:Exception){failed=true}
                    }
                }
                BoxWithConstraints(Modifier.fillMaxSize().clipToBounds(),contentAlignment=Alignment.Center){
                    val bmp=bitmap
                    if(bmp==null){
                        if(failed)Column(horizontalAlignment=Alignment.CenterHorizontally){
                            Text("Pagina non leggibile")
                            TextButton(onClick={failed=false;retry++}){Text("Riprova")}
                        }else CircularProgressIndicator()
                    }else{
                        val density=LocalDensity.current
                        val vw=with(density){maxWidth.toPx()};val vh=with(density){maxHeight.toPx()}
                        val sideways=rotation%180!=0
                        val bw=bmp.width.toFloat();val bh=bmp.height.toFloat()
                        val fit=min(vw/(if(sideways)bh else bw),vh/(if(sideways)bw else bh))
                        val iw=bw*fit;val ih=bh*fit
                        val rw=if(sideways)ih else iw;val rh=if(sideways)iw else ih
                        val active=index==pager.currentPage
                        val zoomNow=if(active)zoom else 1f
                        val state=rememberTransformableState { factor,pan,_ ->
                            if(active){
                                val next=pdfZoom(zoom*factor)
                                val target=if(next<=1f)Offset.Zero else offset+pan
                                zoom=next
                                offset=Offset(pdfPan(target.x,rw,vw,next),pdfPan(target.y,rh,vh,next))
                            }
                        }
                        Box(Modifier.fillMaxSize().transformable(state,canPan={zoom>1.01f},enabled=active)
                            .pointerInput(active){detectTapGestures(onDoubleTap={if(active){if(zoom>1.01f)resetZoom() else {zoom=2f;offset=Offset.Zero}}})},
                            contentAlignment=Alignment.Center){
                            Image(bmp.asImageBitmap(),"Pagina "+(index+1),
                                Modifier.requiredSize(with(density){iw.toDp()},with(density){ih.toDp()})
                                    .graphicsLayer {
                                        scaleX=zoomNow;scaleY=zoomNow;rotationZ=rotation.toFloat()
                                        translationX=if(active)pdfPan(offset.x,rw,vw,zoomNow) else 0f
                                        translationY=if(active)pdfPan(offset.y,rh,vh,zoomNow) else 0f
                                    },contentScale=ContentScale.FillBounds)
                        }
                    }
                }
            } else Box(Modifier.weight(1f).fillMaxWidth(),contentAlignment=Alignment.Center){Text("Nessuna pagina disponibile")}
            if(!immersive){
                Surface(color=Color(0xFF172B3D)){
                    Column(Modifier.fillMaxWidth().padding(horizontal=5.dp,vertical=3.dp)){
                        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically){
                            IconButton(onClick={go(-1)},enabled=!busy&&pager.currentPage>0){Icon(Icons.Default.KeyboardArrowUp,"Pagina precedente")}
                            Text("Pagina "+(pager.currentPage+1)+" / "+count,Modifier.weight(1f),fontSize=13.sp)
                            IconButton(onClick={go(1)},enabled=!busy&&pager.currentPage+1<count){Icon(Icons.Default.KeyboardArrowDown,"Pagina successiva")}
                            IconButton(onClick={resetZoom();rotation=(rotation+90)%360},enabled=!busy){Icon(Icons.Default.RotateRight,"Ruota pagina")}
                        }
                        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.Center){
                            IconButton(onClick={zoom=pdfZoom(zoom/1.25f);offset=Offset.Zero},enabled=zoom>1f){Icon(Icons.Default.ZoomOut,"Riduci zoom")}
                            TextButton(onClick={resetZoom()}){Text((zoom*100).toInt().toString()+"% · Adatta")}
                            IconButton(onClick={zoom=pdfZoom(zoom*1.25f)},enabled=zoom<5f){Icon(Icons.Default.ZoomIn,"Ingrandisci")}
                        }
                        Text(if(zoom>1.01f)"Trascina per leggere · adatta per scorrere" else "Scorri in verticale · pizzica per ingrandire",Modifier.align(Alignment.CenterHorizontally).padding(bottom=5.dp),fontSize=11.sp,color=Color(0xFFADC1D2))
                    }
                }
            }
        }
        if(immersive)Surface(Modifier.align(Alignment.TopEnd).padding(8.dp),shape=androidx.compose.foundation.shape.RoundedCornerShape(12.dp),color=Color(0xDD172B3D)){
            IconButton(onClick={immersive=false}){Icon(Icons.Default.FullscreenExit,"Esci da schermo intero")}
        }
    }
}
