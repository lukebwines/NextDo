# NextDo — Home Assistant add-on

**Versione candidata: 0.1.10-test.** Corregge il trascinamento delle schede Kanban nei progetti condivisi, distinguendo la modifica dello stato dalle modifiche strutturali delle attività. Mantiene le funzioni della 0.1.9-test.

**Versione precedente: 0.1.9-test.** Porta i Gantt dei progetti in evidenza nella Dashboard di ciascun partecipante e aggiunge aggiornamenti rapidi delle attività con stato, nota, autore e data.

**Versione precedente: 0.1.8-test.** Aggiunge il diagramma di Gantt ai progetti, accanto al Kanban, con inizio facoltativo, scadenza, responsabile, stato e attività da pianificare.

**Versione precedente: 0.1.7-test.** Aggiunge spazi personali, assegnazione CdS ai colleghi, scadenze comuni e Project Manager Kanban.

**Versione precedente: 0.1.6-test.** Dashboard rifinita sulla prima proposta grafica approvata: menu con etichette, quattro contatori cliccabili, aggiunta rapida, scadenze compatte, settimana e riepilogo etichette. Aggiunto il ripristino di archivi ZIP esportati da NextDo.

Repository pubblico contenente soltanto codice sorgente. **Nessun codice o nome reale di CdS, database, nota, account o credenziale viene pubblicato.** I dati dell'installazione restano in `/data` sul dispositivo.

## Aggiornamento senza perdere dati

Se NextDo è già installato dal repository GitHub, utilizzare **Aggiorna** nella scheda dell'app Home Assistant dopo l'aggiornamento del catalogo. **Non disinstallare**. Creare e conservare un backup dell'app prima dell'aggiornamento.

La v0.1.3-test riconosce lo schema SQLite della v0.1.2-test e, prima della migrazione, salva una copia in `/data/nextdo-before-full-ui-migration.sqlite3`. Preserve utenti, gruppi, attività e corsi già presenti. La migrazione deve comunque essere verificata sul Raspberry; è stata testata con dati fittizi in un ambiente isolato.

## Sicurezza e limitazioni

Versione sperimentale: non esporre tramite Cloudflare Tunnel, non usare con dati lavorativi reali fino a test di sicurezza e autorizzazione organizzativa. Il modulo promemoria e le ricorrenze richiedono ancora avvio manuale del processo; l'invio email automatico non è abilitato. La build Docker ARM64 non è stata verificata direttamente su Home Assistant OS.

## Sviluppo

```bash
python -m pip install -r nextdo/requirements.txt pytest httpx
PYTHONPATH=nextdo pytest -q tests/test_api.py
```

Si consiglia di usare Home Assistant Ingress; il manifest non espone porte sull'host. Le anagrafiche CdS vanno inserite esclusivamente dall'interfaccia locale.


## Backup NextDo: esportazione e ripristino

Da **Impostazioni**, un amministratore può scegliere **Scarica backup** per esportare database SQLite e allegati in un archivio `nextdo-backup.zip`. Per importare seleziona **Importa backup NextDo**, carica l'archivio e digita **RIPRISTINA**. Prima di modificare il database, NextDo crea automaticamente in `/data` un backup della situazione precedente, con nome `nextdo-before-import-*.zip`. Il database in ingresso è verificato e l'importazione è rifiutata se mancano utenti amministratori, tabelle o allegati richiesti. Dopo l'importazione è necessario eseguire un nuovo accesso.

**Importante:** questa funzione importa SOLO gli ZIP esportati da NextDo, NON i backup `.tar` creati da Home Assistant Supervisor. Per recuperare un precedente `local_nextdo` usare il backup Home Assistant con una procedura separata, senza sovrascrivere direttamente il database in uso.

Limiti provvisori: ZIP massimo 40 MB, contenuto estratto massimo 250 MB. Verificare lo spazio libero del dispositivo e conservare un backup Home Assistant esterno prima del collaudo.

## Interfaccia

I dati di esempio dell'immagine originale non sono preinstallati. Dashboard e grafici visualizzano solo attività ed etichette locali dell'utente. I contatori aprono elenchi filtrati, le note senza scadenza rimangono nel modulo Note.

## Aggiornamento v0.1.4-test

Usare il pulsante **Aggiorna** nell'app già installata dal repository GitHub, senza disinstallare, e conservare prima un backup. La nuova versione non esegue migrazioni ulteriori dello schema SQLite rispetto alla 0.1.3-test. È stata verificata tramite test API locali e lint JavaScript; resta da collaudare in ambiente Home Assistant OS ARM64.

## Correzione risorse in cache, 0.1.5-test

La pagina HTML viene ora servita con `Cache-Control: no-store` e gli URL CSS/JavaScript includono un identificativo calcolato sul contenuto dei file. Questo risolve l'anomalia in cui Home Assistant mostrava la nuova versione dell'add-on ma la precedente dashboard nel browser, senza il pulsante **Importa backup NextDo**. Sono disponibili controlli automatici sulle risorse.

Dopo aver aggiornato NextDo da Home Assistant, riaprire l'interfaccia e, al primo accesso dopo questo rilascio, forzare un refresh (`Ctrl+F5`) oppure usare una finestra privata. Il database non viene cancellato o migrato da questa modifica. In caso di persistenza del problema, verificare il Registro add-on e la versione restituita dall'endpoint `api/build` dopo l'accesso (solo utente autenticato).

## Funzioni aggiunte in NextDo 0.1.6-test

- **Graffetta in Aggiunta rapida:** seleziona subito uno o più documenti e apre la nuova attività con gli allegati già in attesa.
- **Calendario in Aggiunta rapida:** apre la scheda attività e attiva il campo data/ora.
- **Etichetta in Aggiunta rapida:** apre la scheda attività e mette a fuoco il campo etichette.
- **Trascina e rilascia:** trascina PDF, immagini o documenti nella scheda di una nuova attività, di una nota o dell'elemento esistente. Si possono trascinare file anche nel riquadro Aggiunta rapida della dashboard.
- **Caricamento in fase di creazione:** i file sono caricati solo dopo aver salvato l'attività, così non vengono lasciati allegati senza proprietario.
- Formati consentiti: PDF, PNG, JPG, JPEG, WEBP, GIF, BMP, TXT, CSV, DOC, DOCX, XLS, XLSX, PPT, PPTX, RTF, ODT, ODS e ODP. Il limite di upload è 15 MB per file e l'interfaccia consente fino a 10 allegati per singolo salvataggio.
- Se il salvataggio dell'attività riesce ma un caricamento fallisce, la scheda rimane aperta e permette di riprovare soltanto i file non caricati, senza creare un'attività duplicata.
- Per gli allegati già presenti sono disponibili download e rimozione.
- Le richieste di upload continuano a usare l'autenticazione e la protezione CSRF esistenti, senza pubblicare file nel repository.

Questa release modifica interfaccia e lista di estensioni ammesse; non cambia lo schema SQLite né le credenziali. Conservare un backup Home Assistant di NextDo prima dell'aggiornamento. Test visivi e deploy ARM64 devono essere verificati sull'installazione effettiva.

## Progetti, scadenze comuni, CdS e spazio personale (0.1.7-test)

### Configurazione organizzativa

1. Aprire **Impostazioni → + Utente** e creare un account per ogni collega, senza mai caricare account reali nel repository GitHub.
2. Aprire **Corsi di Studio** e inserire/importare l'anagrafica solo nell'installazione locale.
3. Premere **Assegna colleghi** su ciascun CdS e selezionare uno o più utenti. La selezione è modificabile, senza cancellare attività o progetti.
4. I colleghi accedono con credenziali NextDo personali e vedono scadenze dei CdS assegnati, scadenze comuni, progetti a cui hanno accesso e note personali.
5. Per creare **scadenze comuni**, scegliere Ambito: "Comune a tutti i CdS", poi "Completamento globale" o "Separato per CdS". Nel secondo caso ogni collega completa solo i CdS a lui assegnati.
6. Per progetti non collegati ai CdS usare **Progetti → Nuovo progetto → Indipendente dai CdS** e scegliere partecipanti e responsabile. Per quelli CdS usare l'ambito "Uno o più CdS".
7. Il progetto include una **bacheca Kanban** (Da fare, In corso, In attesa, Completato) con spostamento drag-and-drop o modifica dello stato aprendo la scheda.
8. **Il mio spazio** conserva scadenze personali, note/appunti e allegati senza CdS o progetto. Le note personali non sono mostrate ai colleghi né agli amministratori diversi dal proprietario.

### Gestione account

Da Impostazioni ogni utente può modificare la propria password inserendo quella attuale. Un amministratore può reimpostare password altrui, modificare ruoli e disattivare/riattivare utenti. Una variazione di password/ruolo/stato revoca le sessioni dell'account; l'ultimo amministratore non può essere disattivato. La password non viene mostrata in chiaro.

### Sicurezza e migrazione

Prima di modificare il database, la nuova versione crea un backup in `/data/nextdo-before-workspaces-migration.sqlite3` (se non già presente). Nessun database o dato reale deve essere committato su GitHub. Preservare anche un backup esterno dell'add-on Home Assistant prima dell'aggiornamento. Eventuali ZIP importati da una versione precedente di NextDo vengono migrati nel nuovo schema.

Le autorizzazioni sono applicate lato API: un collega non accede alle scadenze di CdS non assegnati, e chi non è autorizzato non può modificare/completare quelle condivise. Una nuova assegnazione CdS aggiorna dinamicamente le autorizzazioni.

**Limiti:** release ancora sperimentale; collaudo su Home Assistant OS ARM64 e prova d'uso multiutente su dispositivo reale necessari prima di impiegare dati lavorativi o consentire accessi esterni. Cloudflare Access con politiche restrittive resta requisito per accesso remoto dedicato.


## Gantt dei progetti (0.1.8-test)

Aprire **Progetti**, selezionare il progetto e usare il selettore **Kanban / Gantt**.

- La vista **Kanban** resta operativa per spostare le attività tra gli stati.
- La vista **Gantt** dispone le attività in una linea temporale, mostra responsabili, stato, oggi, eventuale scadenza complessiva del progetto e una scala di visualizzazione selezionabile.
- Aprire una scheda e inserire **Inizio previsto (facoltativo)** e **Data e ora scadenza**. Una data iniziale successiva alla scadenza viene rifiutata sia dall'interfaccia sia dall'API.
- Le attività con una sola data vengono mostrate come **rombi (milestone)**, senza attribuire loro una durata arbitraria.
- Le attività senza alcuna data rimangono nella sezione **Da pianificare**. Le date esistenti rimangono inalterate.
- La barra mostra l'intervallo pianificato e il colore indica lo **stato** della scheda, non una percentuale di avanzamento. Le informazioni sul completamento del progetto rimangono basate sulle attività concluse/totali.
- Selezionare una barra o una riga per aprire la scheda e aggiornare date, descrizione, assegnatario e stato, nel rispetto dei permessi esistenti.

**Migrazione:** i dati da 0.1.7-test vengono preservati; prima di aggiungere la colonna locale `start_at` viene creata, quando necessaria, la copia SQLite `/data/nextdo-before-gantt-migration.sqlite3`. Non cancellare la copia precedente e creare sempre un backup dell'add-on Home Assistant prima dell'aggiornamento.

**Limiti della prima versione:** la pianificazione si modifica dalle schede, non trascinando le barre; dipendenze tra attività, percorso critico e avanzamento percentuale per singola attività non sono ancora implementati. È necessario collaudare l'interfaccia sull'installazione ARM64 Home Assistant prima dell'uso con i colleghi.


## Dashboard dei colleghi e Gantt in evidenza (0.1.9-test)

La **Dashboard** di ogni collega mostra i Gantt dei progetti a cui ha accesso che sono stati contrassegnati come in evidenza. In **Progetti → Modifica progetto**, i responsabili possono attivare o disattivare **Mostra Gantt nella Dashboard dei partecipanti**. I progetti esistenti sono inizialmente in evidenza e possono essere esclusi dalle rispettive dashboard. Le note personali restano private e non compaiono nei Gantt.

La sezione **Le mie attività di progetto** mostra le attività assegnate direttamente all'utente e quelle non assegnate che ha creato lui, ordinate prioritariamente per stato e scadenza. Il pulsante **Aggiorna** permette di scegliere lo stato (Da fare, In corso, In attesa, Completata) e di aggiungere una breve nota operativa. La scheda conserva la cronologia degli aggiornamenti con **autore, data, stato precedente/nuovo e commento**, visibile soltanto agli utenti con accesso alla relativa attività.

Nel **Kanban**, le schede modificabili possono essere trascinate tra colonne oppure aggiornate tramite **Aggiorna stato**. Il trascinamento aggiorna lo stato sul server e registra la variazione nello storico, anche se il collega non aggiunge una nota. Sulle scadenze a completamento separato per CdS, lo spostamento a Completata non sostituisce la conferma dei singoli CdS.

Il **Gantt non supporta ancora il trascinamento temporale delle barre**: cliccando sulla barra si apre la scheda per modificare le date di inizio e fine. La funzione è stata volutamente distinta dal trascinamento Kanban, che serve invece a cambiare lo stato.

**Migrazione:** il database viene esteso senza cancellare i progetti; se occorre aggiungere il flag di evidenza viene creato il backup SQLite `/data/nextdo-before-featured-projects-migration.sqlite3`. Prima dell'installazione della 0.1.9-test eseguire anche un backup dell'add-on Home Assistant. Le nuove funzioni richiedono un collaudo nell'interfaccia web e sui permessi con account di prova prima dell'uso quotidiano dei colleghi.


## Correzione del trascinamento Kanban (0.1.10-test)

In **Progetti → Kanban**, i membri autorizzati di un progetto e i colleghi assegnati ai CdS del progetto possono spostare le **attività senza assegnatario** tra *Da fare / In corso / In attesa / Completata*, anche se il proprietario della scheda è l'amministratore. Il trascinamento è disponibile sulle attività espressamente assegnate al proprio account. Le schede di altri colleghi restano in sola lettura.

Le attività trascinabili mostrano **«⋮⋮ Trascina»** e il pulsante **«Aggiorna stato»** come alternativa affidabile quando il browser o un dispositivo non gestisce il drag-and-drop. Le schede bloccate mostrano invece **«Sola lettura»** e una spiegazione. La selezione dello stato è salvata sul server e tracciata nello storico. Per il completamento separato per CdS è necessario confermare ogni CdS nella scheda, anziché trascinare direttamente su *Completata*.

**Sicurezza:** il permesso di modificare lo stato e scrivere note di avanzamento (`can_move`) non autorizza a cancellare, riassegnare o modificare la struttura della scheda (`can_edit`). Per poter aggiornare le attività non assegnate, il collega deve essere un membro esplicito del progetto o un collega assegnato a uno dei CdS associati. La sola visibilità di un progetto comune non concede automaticamente permessi di modifica.

Aggiornare l'add-on da Home Assistant dopo un backup. Non modificare il database né disinstallare l'add-on. Il comportamento nel browser reale va confermato con un account di prova.
