# NextDo — Home Assistant add-on

**Versione candidata: 0.1.18-test.** Sposta la sezione I miei progetti e avanzamenti e i relativi Gantt alla fine della Dashboard, dopo scadenze, aggiunta rapida, settimana ed etichette. Nessuna modifica ai dati o al criterio di aggiornamento del Gantt.

**Versione precedente: 0.1.17-test.** Vista Progetti compatta, ricerca e filtri per CdS/responsabile, dettaglio Kanban/Gantt separato. Nessuna modifica al database.

**Versione candidata: 0.1.15-test.** Precompila mediante spunte i CdS gestiti abitualmente da ogni collega nel modulo progetto, lasciando indipendenti le assegnazioni salvate per ciascun progetto.

**Versione precedente: 0.1.14-test.** Permette di assegnare i colleghi a uno o più CdS direttamente nel progetto e genera automaticamente le righe di avanzamento per ciascun CdS nell'esportazione JSON.

**Versione precedente: 0.1.13-test.** Esporta ogni progetto NextDo in JSON, con identificativi stabili delle attività e un nome file nuovo a ogni download, compatibile con il flusso Power Automate testato.

**Versione precedente: 0.1.12-test.** Avvia un collegamento Microsoft Lists di prova in sola lettura, con autorizzazione delegata temporanea e identificazione degli elenchi SharePoint. Non modifica né pubblica alcun dato sul tenant Microsoft 365.

**Versione precedente: 0.1.11-test.** Password da almeno 8 caratteri per gli utenti ordinari, minimo 12 per gli amministratori.

**Versione precedente: 0.1.10-test.** Corregge il trascinamento delle schede Kanban e introduce un selettore dello stato alternativo.

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


## Correzione Kanban e cambio di stato (0.1.10-test)

In **Progetti → Kanban**, le schede contrassegnate dal simbolo **⠿** possono essere trascinate nelle colonne Da fare, In corso, In attesa e Completata. Le colonne si evidenziano durante il trascinamento. In alternativa il menu **Stato** nella scheda aggiorna immediatamente lo stato e funziona anche sui dispositivi che non supportano il trascinamento HTML5.

**Autorizzazioni:** amministratori e responsabili di progetto gestiscono le attività del progetto. Un partecipante può cambiare lo stato delle attività assegnate a sé e di quelle non ancora assegnate nel proprio progetto. Per i progetti associati a CdS, può anche far avanzare attività non assegnate se è responsabile di uno dei CdS del progetto. Le attività affidate esplicitamente a un altro collega sono visibili, ma non trascinabili dai semplici partecipanti. Il cambiamento dello stato non concede automaticamente il permesso di modificare o cancellare l'intera scheda, il progetto o gli allegati.

Le scadenze a **completamento separato per CdS** non possono essere chiuse o riaperte trascinandole: utilizzare i pulsanti di completamento dei singoli corsi. Ogni cambio di stato viene registrato nella cronologia di avanzamento.

**Verifiche:** test API per membri, assegnatari, responsabili e accessi negati, oltre a una prova automatizzata con Chromium che trascina realmente una scheda e verifica il salvataggio sul server. La suite non sostituisce il collaudo sul proprio Raspberry: prima dell'aggiornamento di NextDo eseguire un backup dell'add-on, poi usare Aggiorna senza disinstallare.


## Password per ruolo (0.1.11-test)

- Ruolo **Utente**: minimo 8 caratteri in fase di creazione, modifica autonoma e reimpostazione da parte dell'amministratore.
- Ruolo **Amministratore**: minimo 12 caratteri in fase di primo avvio, creazione, modifica autonoma e reimpostazione.
- La promozione di un normale utente ad amministratore richiede l'impostazione contestuale di una nuova password da almeno 12 caratteri; le vecchie sessioni vengono revocate.
- Il login continua ad accettare la lunghezza delle password precedentemente create (nessuna interruzione di compatibilità).
- Usare passphrase non riutilizzate, protezione Cloudflare Access con verifica d'identità e limitazione degli accessi; il minimo di 8 caratteri non sostituisce questi controlli.


## Microsoft Lists — primo collegamento di prova (0.1.12-test)

La sezione **Impostazioni → Microsoft Lists — collegamento di prova** è visibile soltanto agli amministratori NextDo. Per questa versione l'integrazione è **rigorosamente in sola lettura** e non crea liste, colonne, attività o sincronizzazioni automatiche.

### Prerequisiti Microsoft 365

Occorre un'applicazione Microsoft Entra registrata/autorizzata dall'organizzazione, configurata come **client pubblico con flusso codice dispositivo abilitato**, e il permesso delegato Microsoft Graph **Sites.Read.All** (l'organizzazione può richiedere il consenso dell'amministratore). Recuperare l'**ID tenant** e l'**ID applicazione (client)**, entrambi GUID. Non servono password, segreti client o credenziali Microsoft dentro NextDo.

Istruzioni: inserire gli identificativi e l'indirizzo del sito SharePoint (è accettato anche il link alla lista condivisa del sito), salvare la configurazione, scegliere **Connetti Microsoft 365**, aprire il sito Microsoft indicato e inserire il codice temporaneo. Tornare su NextDo e scegliere **Verifica autorizzazione**, poi **Elenca liste** e selezionare la lista di prova già creata. **Verifica colonne** effettua esclusivamente richieste GET.

### Misure di sicurezza e limitazioni

- Soltanto gli amministratori NextDo possono configurare e collegare l'integrazione.
- I token Microsoft sono conservati **solo in memoria del processo** e scadono; non vengono salvati in SQLite, nel repository o nei backup. Dopo un riavvio è necessario autorizzare nuovamente il collegamento.
- Il file locale di configurazione (senza token) è creato in `/data/microsoft-lists-pilot.json` con permessi 0600.
- Il collegamento usa soltanto endpoint Microsoft predefiniti, valida le URL SharePoint e non segue reindirizzamenti che potrebbero esporre i token.
- Non si deve utilizzare l'app con dati di lavoro reali senza validazione da parte dei servizi informatici dell'Ateneo.
- **Passaggi successivi non ancora disponibili:** creazione automatica delle colonne, pubblicazione delle attività, vista bacheca e importazione degli stati. Per creare colonne Graph richiede almeno il permesso delegato `Sites.Manage.All`; per aggiungere o aggiornare le righe `Sites.ReadWrite.All`. Sono permessi ampi, da approvare espressamente prima di implementarli e richiederli. La successiva sincronizzazione dovrà scrivere solo i campi di pianificazione di NextDo e mai sostituire lo stato o le note dei colleghi.


## Esportazione progetti verso Microsoft Lists tramite Power Automate (0.1.13-test)

Nel progetto desiderato, il responsabile o un amministratore può scegliere **Esporta JSON per Lists**. Il browser scarica un nuovo file `nextdo-project-{id}-{timestamp}-{suffix}.json`, da caricare manualmente nella cartella SharePoint `Documenti condivisi/NextDo_Sync` configurata nell'esperimento. Nessuna trasmissione automatica o registrazione di app Entra è richiesta per questa modalità manuale. Il pulsante non è visibile ai partecipanti senza permessi di gestione; anche l'endpoint del download controlla i permessi.

Il JSON usa lo schema già verificato con il flusso Power Automate: `schema_version=1.0`, `source=NextDo`, `project.{id,title}` e l'array `tasks` con `id,title,status,due_at`. Gli ID sono permanenti nel database NextDo: `NEXTDO-P{project_id}` e `NEXTDO-T{task_id}`. Il nome del file cambia a ogni esportazione in modo che il trigger SharePoint **Quando viene creato un file (solo proprietà)** rilevi anche i nuovi caricamenti, mentre l'ID dell'attività non cambia, consentendo il controllo anti-duplicazione.

**Minimizzazione dei dati:** il file contiene titoli dei progetti e delle attività, stato e scadenza. Non esporta descrizioni, note di avanzamento, dati degli utenti o allegati. Controllare i titoli prima di caricarli sul sito istituzionale. Non esportare attività con contenuti riservati o personali senza autorizzazione.

**Limiti attuali:** l'integrazione è **a senso unico** e richiede l'upload manuale del JSON. Il flusso Microsoft Lists sperimentale crea solo i campi **Titolo** e **NextDoID**, e salta completamente gli elementi esistenti; non aggiorna in SharePoint gli stati, i titoli e le scadenze di attività già importate. Non recupera ancora gli stati aggiornati dai colleghi in NextDo. Nessun collegamento con l'API Microsoft viene effettuato dal pulsante di esportazione. Per una vera sincronizzazione bidirezionale serve una fase ulteriore con autorizzazioni appropriate e regole di ownership dei campi.


## NextDo 0.1.14-test — Responsabili CdS a livello di progetto

Nel modulo **Progetti → Modifica progetto**, la sezione **Responsabili dei singoli CdS** permette di scegliere le coppie **collega + Corso di Studio**. Un collega può gestire più CdS, e più colleghi possono essere assegnati al medesimo CdS. Le assegnazioni sono registrate a livello di progetto e valgono automaticamente per tutte le attività del progetto, senza richiedere altre selezioni nei moduli delle singole attività. I CdS e gli utenti provengono soltanto dalle anagrafiche locali di NextDo; nel repository non sono inseriti nominativi reali.

I destinatari assegnati possono visualizzare il progetto e le attività pertinenti senza acquisire automaticamente permessi per modificarne le impostazioni o spostare gli stati globali in NextDo. Gli **Altri partecipanti** continuano a seguire le regole di accesso già esistenti: se non devono poter intervenire sulle attività globali, non devono essere aggiunti come partecipanti generici. Il cambio degli incarichi non altera gli ID delle attività nel database e conserva la struttura precedente dei progetti non ancora configurati.

La funzione **Esporta JSON per Lists** ora genera per ciascuna attività un record con ID stabile **`NEXTDO-T{task_id}-C{course_id}`** per ogni CdS distinto nel progetto. Se più colleghi seguono lo stesso CdS si crea comunque **una sola riga per coppia attività–CdS**, con il campo aggiuntivo **`responsible_user_ids`** che contiene i relativi identificativi interni NextDo. Sono inoltre esportati **`course_code`**, **`course_name`** e **`project_title`**, sempre attingendo ai dati dell'installazione. Non sono esportati nomi utenti, email, descrizioni, note, né allegati. Senza assegnazioni restano gli ID e la struttura JSON precedenti, compatibili con i primi test.

**Configurazione successiva necessaria su Microsoft Lists e Power Automate:** aggiungere nella lista `test` le colonne **CdS**, **Progetto** e un campo Persona/collegamento all'account Microsoft 365, con mappatura autorizzata tra gli ID NextDo e le utenze Microsoft. Aggiornare l'azione **Crea elemento** del flusso per valorizzarle solo alla prima importazione. La colonna **Stato** e le note compilate dai colleghi in Microsoft Lists devono rimanere di proprietà di Lists, senza essere sovrascritte da nuovi upload. Fino a tale configurazione il JSON contiene i dati, ma il flusso importa soltanto titolo e ID, quindi **non dispone ancora di viste personali affidabili per i colleghi**.

**Prima di importare un progetto già presente in Lists:** l'aggiunta di destinazioni CdS cambia gli ID delle righe da `NEXTDO-T{id}` a `NEXTDO-T{id}-C{course_id}`. Il vecchio record generico non sarà cancellato né convertito dal flusso; bisogna archiviarlo o riconciliarlo manualmente nel collaudo. La rimozione di assegnazioni dal progetto, inoltre, non elimina elementi già esistenti in Lists. Non usare il nuovo export con dati reali finché le colonne e la mappatura utenti non sono state collaudate.

**Ambito attuale:** NextDo → file JSON scaricato manualmente → SharePoint → Power Automate → Microsoft Lists. La sincronizzazione di ritorno per aggiornare la dashboard NextDo con gli stati per singolo CdS è ancora da realizzare. Gli stati globali nel Kanban NextDo non costituiscono un aggregato delle lavorazioni Microsoft Lists.


## NextDo 0.1.15-test — CdS predefiniti, modificabili con spunte per progetto

L'anagrafica **Corsi di Studio → Assegna colleghi** continua a memorizzare la distribuzione ordinaria dei CdS: tali associazioni sono persistenti fino a successiva modifica esplicita. Non occorre reinserirle a ogni progetto.

In **Progetti → Nuovo progetto / Modifica progetto → Responsabili dei singoli CdS**, usare **+ Aggiungi collega** e selezionare il collaboratore. NextDo mostra i CdS attivi e **preseleziona con una spunta** quelli associati abitualmente al collega. L'utente può rimuovere i CdS non interessati e aggiungerne altri per il singolo progetto. Il pulsante **Ripristina predefiniti** ripropone le associazioni correnti, solo quando richiesto.

**Salvataggio separato e conservativo:** le coppie collega–CdS selezionate sono registrate nella tabella del progetto, che rimane indipendente dall'anagrafica generale. Quando si riapre un progetto si vedono le selezioni effettivamente salvate, **anche se nel frattempo l'anagrafica generale è cambiata**. Solo la modifica esplicita del progetto ne aggiorna i destinatari e quindi i record delle successive esportazioni. La disattivazione di un CdS o utente va gestita prima del successivo salvataggio di un progetto interessato, secondo la validazione esistente.

**Accesso ai suggerimenti:** amministratori possono vedere tutte le associazioni attive; altri utenti vedono i suggerimenti delle associazioni relative soltanto ai propri CdS. Le assegnazioni degli altri CdS non vengono pubblicate a tutti gli utenti. Il pulsante **+ Aggiungi collega** non modifica l'anagrafica generale.

**Invariato il flusso Microsoft Lists:** tutte le attività di un progetto continuano a essere esportate con righe indipendenti per CdS. L'importazione SharePoint di prova va adattata per CdS, Progetto e responsabili prima di usare dati reali. Non è stata implementata la sincronizzazione degli stati da Lists a NextDo.


## NextDo 0.1.16-test — selezione CdS con spunte e colleghi automatici

In **Progetti → Nuovo progetto** scegliere l'ambito **Uno o più CdS** e selezionare i corsi interessati tramite le spunte **CdS coinvolti**. Per ogni corso appena selezionato NextDo propone automaticamente i colleghi già configurati in **Corsi di Studio → Assegna colleghi**. Nel riepilogo **Colleghi coinvolti** sono mostrati i nomi proposti e i relativi CdS. Se un corso non ha ancora un collega associato, NextDo lo segnala senza inventare un responsabile.

La sezione **Modifica assegnazioni per questo progetto (facoltativo)** permette eccezioni specifiche: aggiungere o togliere colleghi e CdS senza modificare l'anagrafica generale. Deselezionando un CdS vengono rimosse dalle assegnazioni del progetto le spunte relative a quel corso, senza cancellare i dati dell'anagrafica. Riattivando un CdS vengono riproposti i suoi responsabili generali.

**Tutela dei progetti esistenti:** aprendo un progetto NextDo visualizza la sua fotografia salvata, senza riscriverla quando cambiano le associazioni generali. Le proposte automatiche intervengono soltanto quando un CdS viene aggiunto alla selezione del progetto. Non sono state modificate le tabelle del database né la sincronizzazione Microsoft Lists: rimane l'esportazione manuale in JSON.


## NextDo 0.1.17-test — Progetti in due livelli

La pagina **Progetti** mostra come impostazione iniziale un elenco compatto, senza renderizzare sotto di esso il Kanban del primo progetto. Ogni riga riporta titolo, ambito, CdS collegati, responsabile (se disponibile), stato, numero di attività completate e avanzamento. I filtri locali comprendono **Attivi / Completati / Tutti**, ricerca per titolo/ambito/CdS/responsabile, selezione del singolo CdS e del responsabile.

Selezionando una riga si apre **il solo progetto scelto**, con tutte le funzioni precedenti: responsabilità per CdS, esportazione JSON per Lists, modifica, nuove attività, Kanban e Gantt. **← Torna ai progetti** ritorna all'elenco. Anche la navigazione laterale su **Progetti** apre l'elenco, mentre **Apri Kanban** dalla Dashboard continua ad aprire direttamente il progetto corretto.

L'implementazione è soltanto lato interfaccia: non esegue migrazioni SQL, non modifica le assegnazioni e non cancella attività. Gli elenchi/filtri sono limitati ai progetti che l'API dell'utente autorizzato restituisce. La pubblicazione su GitHub non aggiorna automaticamente l'app Home Assistant; usare **Aggiorna** senza disinstallarla e provare il funzionamento con utenti di test.
