# NextDo Android — roadmap prioritaria

## Priorità concordate il 25 novembre 2026 — APK prima del Web

Questa sezione sostituisce l'ordine delle priorità precedenti; le sezioni storiche rimangono come registro degli sviluppi. Obiettivo: un solo sistema scalabile, retrocompatibile, con Raspberry come fonte autorevole e fruibilità Android anche senza rete. Prima della partenza prevista a dicembre: consolidare le funzionalità essenziali e sospendere le aggiunte non indispensabili se il collaudo non è concluso.

| Priorità | Intervento | Criterio di completamento | Stato |
| --- | --- | --- | --- |
| P0 | Collaudo APK 0.2.2-test | Verificare sul Samsung sblocco biometrico, PIN soltanto quando necessario, lettore PDF a schermo intero, zoom, rotazione, pagine, download, condivisione, apertura esterna, modalità aereo e ritorno all'app. Firma e test CI superati; conservare configurazioni e dati aggiornando senza disinstallare. | Release pubblicata; collaudo fisico da completare |
| P0 | Aggiornamenti APK affidabili | Verifica manuale e automatica delle release firmate; distinguere aggiornamento assente, errore di rete e metadati non leggibili. Non ridurre controlli di firma, hash o versionCode. | Da verificare |
| P1 | Tipologie dinamiche Web–APK | Leggere il catalogo privato per utente dal Raspberry, renderizzare icone e campi specifici, modificare campi e tipologie delle prenotazioni online; mantenere dati storici, formati ZIP e compatibilità. I modelli definiti sul Web sono utilizzabili nell'APK senza nuova release per ogni modello; salvare una copia del catalogo per la consultazione offline. Gestione del catalogo direttamente da Android come estensione successiva. | Da sviluppare |
| P1 | Assicurazione ed emergenze | Accesso rapido dalla panoramica Android a polizza originale, contatti e procedura di assistenza, anche offline; nessuna nuova sezione principale, nessun dato inventato. | Da sviluppare |
| P1 | Sincronizzazione offline | Confrontare revisione locale e server, mostrare data dell'ultima sincronizzazione, segnalare copie obsolete e aggiornare quando online e autorizzati. Conservare copia cifrata valida in caso di errore; aggiornare insieme manifest, allegati e diario; testare sostituzione PDF e assenza rete. Nessuna sovrascrittura di modifiche locali non riconciliate. | Da sviluppare |
| P1 | Sostituzione documenti PDF (supporto Web/server) | Azione esplicita Sostituisci PDF con anteprima/conferma e controllo revisione; preservare collegamenti esistenti, validare PDF, gestire eventuale uso condiviso tra prenotazioni e guide, evitare duplicati; nessuna cancellazione automatica dei documenti ancora collegati. Aggiornare copie Android tramite sincronizzazione. | Implementata nel codice Web/server 0.2.6-test; test e collaudo da verificare |
| P2 | Budget e spese | Previste/sostenute/residuo, categorie, multivaluta senza conversioni implicite, ricevute e consultazione mobile. | Parziale sul Web; da estendere |
| P2 | Spazio e archivio | Monitoraggio dimensioni, allegati, export, backup/ripristino e viaggi conclusi; nessuna eliminazione automatica non autorizzata. | Da sviluppare |
| P3 | Moduli personali | Agenda, promemoria e note personali, mantenendo separazione dall'area professionale. | Da sviluppare |

### Stato documenti (verificato nel codice)
- Web 0.2.5-test: upload di PDF con nome univoco; un nome già presente genera 409. Si può associare un nuovo PDF dalla modifica della prenotazione; il precedente non è eliminato automaticamente. Il caricamento e l'associazione incrementano la revisione del viaggio.
- Android 0.2.2-test online: all'apertura rilegge il manifest dal server e alla consultazione scarica il PDF associato dal Raspberry. Un viaggio già aperto può avere riferimenti non aggiornati: riaprirlo.
- Offline: snapshot ZIP cifrato, aggiornabile manualmente dalla schermata Home del viaggio online tramite Scarica / aggiorna offline; non c'è ancora sincronizzazione automatica. I file esportati in Download o app esterne sono copie indipendenti.
- Evitare nuove sezioni per ciascuna categoria: un unico archivio prenotazioni, modelli riutilizzabili e documenti associati.

## Obiettivo
Un'unica app NextDo, con dashboard generale e due aree separate, come sul web. Viaggi rimane un modulo personale; nessuna perdita di dati o funzioni esistenti. L'identificativo uk.archis.nextdoviaggi, la firma APK, i tag android-v e gli asset nextdo-viaggi.apk/json restano invariati per compatibilità.

| Versione Android indicativa | Obiettivo | Stato |
| --- | --- | --- |
| 0.1.7-test | Nuovo nome e icona; dashboard, Professionale, Personale, Impostazioni, navigazione modulare; Viaggi integro | Integrata, CI superata |
| 0.1.8-test | Associazione professionale esplicita, API dedicate e minimali, agenda settimanale, scadenze e appuntamenti anche da verificare, arretrati, priorità | Integrata, CI superata |
| 0.1.9-test | Avvisi in background e locali, canali di priorità, ripetizione critica e presa visione locale, preferenze e permessi Android | Integrata, CI superata; collaudo fisico richiesto |
| 0.1.10-test | Push FCM e presa visione condivisa per revisione | Implementata, test e configurazione Firebase richiesti |
| 0.1.11-test | Agenda, note e promemoria personali con accesso separato | Da sviluppare |
| Successive | Ripresa roadmap Viaggi | Sospesa |

## Sicurezza e vincoli
- Nessuna estensione automatica dei token Viaggi. Autorizzazione professionale specifica, revocabile e limitata ai dati effettivamente accessibili dall'utente sul web. Non esporre API amministrative, cookie web, credenziali o database.
- Dati professionali e personali distinti anche in eventuali cache, notifiche e log. Nessun dettaglio sensibile nelle notifiche sullo schermo bloccato per impostazione predefinita. Non includere dati privati o professionali nel repository.
- Il Raspberry resta fonte autorevole: includere le voci da verificare, non confondere mancanza di connessione con agenda vuota. Fuso orario, deduplicazione e aggiornamenti da verificare.
- Notifiche realmente funzionanti ad app chiusa richiedono una strategia push e promemoria locali da progettare. Avvisi ripetuti, suoni prolungati e modalità allarme dipendono dai permessi, dalle regole Android e dal risparmio energetico. Non promettere aggiramento delle impostazioni di sistema.
- Prima del rilascio test di regressione Viaggi, firma permanente, aggiornamento senza disinstallazione, collaudo Samsung. La 0.1.7-test non attiva ancora API professionali o notifiche.

Numerazioni indicative; priorità: completare l'area professionale e gli avvisi prima di riprendere gli sviluppi Viaggi.

## Agenda professionale — server 0.1.39-test / Android 0.1.8-test
Pairing dedicato nella Dashboard web (codice 5 minuti, token revocabile 30 giorni, hash lato server e Keystore Android); nessuna credenziale Viaggi può accedere all'agenda. Password cambiata, account disattivato/cancellato e restore invalidano l'accesso. Le voci scope personal del gestionale web sono attività lavorative private, incluse perché anche le email da verificare usano tale scope; esclusi note e Viaggi. Agenda aperta paginata in sola lettura, dettagli su richiesta, timezone server, senza orario inventato, filtri settimana/urgenti/scadute/trascorsi/da verificare/senza data/tutte. Refresh all'apertura Home/Lavoro e manuale; nessuna sincronizzazione in background, cache professionale persistente o notifica ancora. Collaudare gateway HTTPS per /api/mobile/v1/work/, associazioni distinte, revoca e aggiornamento APK.

## Avvisi professionali — server 0.1.40-test / Android 0.1.9-test
Opt-in in Impostazioni dopo pairing e permesso Android. Credenziale limitata ai soli avvisi (chiavi opache, priorità, tipo, stato review e tempi), separata da Viaggi e dall'agenda, revocabile con il dispositivo o disattivazione. Nessun titolo o descrizione nelle notifiche. Keystore separato senza autenticazione biometrica per consentire il background; nessuna credenziale di lettura agenda memorizzata in tale vault. WorkManager circa ogni 15 minuti, sveglie locali non esatte per i promemoria e ripetizioni, cache cifrata dei soli metadati valida fino a 24h dall'ultimo contatto e non oltre scadenza token. Avvisi urgenti/review immediati al rilevamento, scadenze 24h e termine, appuntamenti con orario anche 1h/15min. Data senza orario: promemoria 09:00 nel fuso server, non orario effettivo. Critici ripetuti 15/30/60min fino a presa visione locale per quella revisione; nuova modifica può riattivare. Presa visione non cambia stato task sul server. Canali Android e prova, limiti per non saturare il telefono. Nessuna garanzia di tempi esatti sotto Doze/risparmio energetico, app arrestata forzatamente o permessi negati. Nessun servizio push esterno introdotto; push immediato richiederà una scelta dedicata (es. FCM). Collaudo fisico Samsung obbligatorio, soprattutto schermata bloccata, revoca, modalità offline, riavvio e risparmio energetico.

## Push e presa visione — server 0.1.41-test / Android 0.1.10-test
Presa visione per utente e revisione (non completamento); Android, notifica e web condividono lo stesso stato; offline accoda la presa visione e ritenta. Push opzionale FCM HTTP v1: amministratore carica i due JSON Firebase sul Raspberry, chiave privata fuori dal repository e APK. Il server verifica le modifiche visibili per dispositivo ogni 5 secondi e invia solo un segnale generico; WorkManager aggiorna dal Raspberry e mantiene il fallback periodico. Nessuna garanzia di latenza, FCM/Android possono ritardare. Il token di background non può leggere dettagli; revoca/disattivazione e restore eliminano iscrizioni. Configurazione reale e test fisico ancora necessari. Rinvio e completamento attività da Android rimangono successivi.

### Pubblicazione 0.1.10-test
Per questa sola versione, la pipeline firmata può partire anche da un merge esplicitamente marcato `Publish Android 0.1.10-test:` su main, dopo i test PR superati. Mantiene la firma permanente, il package ID e il normale comando manuale per i rilasci successivi. Nessuna modifica alle chiavi.

## 0.1.11-test — Allarmi professionali potenziati (priorità utente)
Server invariato, impostazioni locali per durata/ripetizione/suono/vibrazione/schermo/notifica. Full-screen e promemoria esatti solo se Android autorizza, servizio audio temporaneo con fallback notifica. Presa visione sincronizzata; silenziamento distinto. Test CI e collaudo Samsung obbligatori. La roadmap personale è rinviata a una release successiva.

## PDF multipli — Web 0.2.7-test / Android 0.2.3-test
Il PDF storico rimane associato. Altri PDF possono essere caricati nell'archivio e collegati alla stessa prenotazione, con etichette personalizzabili. Gestione Web, consultazione Android online e nelle copie offline aggiornate. Scollegamento senza cancellazione del file; sostituzione esplicita con conferma. Nessuna migrazione distruttiva. Sincronizzazione automatica offline e modifica allegati in Android restano successive. Test e collaudo da verificare.

## Area personale — accordo del 25 novembre 2026

- Dashboard professionale invariata all'apertura; nessun dettaglio di attività private.
- Dashboard personale semplificata: Attività, Scadenze, Appuntamenti, Viaggi. Conservare tutte le funzioni Viaggi.
- Aspetto indipendente: tema chiaro/scuro, quattro palette, tinta unita/sfumatura/fotografia, ripristino. Preferenze sul server privato per profilo, accesso protetto anche Android; nessun invio a servizi esterni. Prima fase in sviluppo, collaudo necessario.
- Fase funzionale ancora da sviluppare: instradamento da mittenti SMTP autorizzati configurabili (nessun indirizzo reale nel repository), separazione effettiva di API, dati, notifiche, esportazioni e permessi; stato Da verificare; riclassificazione controllata dei record storici senza duplicazioni; spostamento esplicito tra aree. Non confondere scope=personal (attività professionale individuale) con area privata. Nessuna migrazione automatica prima del collaudo.

### Avanzamento ramo di sviluppo `personal-appearance`
- Agenda privata su tabella distinta, accesso Web dopo sblocco e API Android con sessione personale; creazione, modifica, eliminazione e completamento su entrambe le interfacce. Tre categorie (attività, scadenza, appuntamento); data e ora non inventate.
- Configurazione Cloudflare: selezione dei mittenti personali fra quelli già autorizzati; destinazione fissata al momento dell'acquisizione, legata all'identità personale stabile; impronte separate dal Professionale. Nessun indirizzo reale nel codice. Gli altri mittenti autorizzati restano professionali. Le email personali non compaiono nel registro professionale; il testo dei casi non classificati è disponibile nella descrizione dell'impegno privato. Le proposte ricevute restano Da verificare.
- Non ancora completati: spostamento tra aree e migrazione guidata dello storico, notifiche personali/ICS separate, verifica backup/ripristino e cancellazione account, collaudo completo Web e Samsung. Gli impegni storici non vengono modificati automaticamente. Non rilasciare finché i controlli e i requisiti di isolamento non siano verificati.

### Trasferimento controllato (bozza)
Trasferimenti individuali semplici e riclassificazione per gruppo di email già ricevute, con conferma e transazione unica. Blocchi espliciti per collegamenti, metadati non compatibili, duplicati, invii ICS in corso, mittenti misti o attività mancanti. Non ritira invii/copie già esportati. Web: anteprima nell'area protetta Personale; Android: collegamento al web; gli endpoint di trasferimento richiedono la sessione web protetta, senza estendere il token Viaggi ai dati professionali. Gli impegni privati importati da email non sono ancora trasferibili in Professionale per preservarne la provenienza.

### Backup gestionale privato (bozza)
Il backup ZIP del gestionale include l'agenda privata: esportazione e ripristino richiedono lo sblocco personale se sono presenti dati privati e sono consentiti solo all'amministratore che ne è l'unico proprietario. Il ripristino rifiuta archivi che perdono identità personali esistenti. Non comprende il database Viaggi, le preferenze grafiche o le chiavi locali: per il backup completo usare Home Assistant. Nessun ripristino reale eseguito.

### Avvisi personali (bozza)
Android: opt-in, canale e token separati, controllo WorkManager ogni 15 minuti indicativi e all'apertura, contenuto generico e impronte opache. Avvisi review/urgenti e finestre 24h, 1h/15min per appuntamenti con ora, scadenza. Non è un allarme esatto e non usa FCM. Web: riepilogo promemoria in area privata. Nessun ICS personale automatico. Collaudo fisico e CI necessari.

## Rilascio di prova — Web 0.2.10-test / Android 0.2.5-test (versionCode 20)
Aggiornare prima l'add-on, poi l'APK firmata senza disinstallarla. Prima dell'aggiornamento effettuare un backup completo di NextDo in Home Assistant (database, archivio Viaggi, allegati, chiavi e configurazioni). Riferimento sorgente precedente: ramo rollback-before-personal-0.2.10; APK precedente android-v0.2.4-test. Il downgrade Android non è normalmente consentito senza disinstallazione: preferire una build correttiva firmata con versionCode superiore; per il ripristino server usare il backup completo precedente, tenendo conto dei dati creati dopo. Nessuna migrazione storica automatica. Configurare i mittenti personali tra quelli autorizzati in impostazioni email, poi testare un inoltro da ciascuna area. Verificare sul telefono tema, foto, agenda, notifiche e Viaggi; gli avvisi personali non sono esatti e non inviano ICS automaticamente. Trasferimenti sul web per elementi compatibili; provenienza delle email private verso Professionale non ancora supportata.


## Android 0.2.6-test — date e orari italiani (versionCode 21)
**Ambito APK soltanto:** nessuna variazione di server, database, API, formati persistenti, permessi, notifiche o calcolo delle scadenze. Stessa firma e package. Versione di riferimento: android-v0.2.5-test, sorgente conservato in rollback-before-android-0.2.6. Per un eventuale ripristino Android preferire una build correttiva firmata con versionCode superiore; non disinstallare per forzare il downgrade.

### Inventario e interventi
- Dashboard e Professionale: data odierna, ultima sincronizzazione, elenco e dettaglio, intervallo settimana, filtro calendario con salto a data. Agenda professionale resta in sola lettura, salvo le azioni già presenti.
- Personale: attività, scadenze, appuntamenti; data e ora separate, picker nativi, precompilazione valori esistenti; nuove voci con data obbligatoria preselezionano oggi, nelle voci facoltative la data resta assente fino a conferma. L'orario non è assegnato automaticamente. Rimozione data dove consentita e conseguente rimozione ora; precisione originale conservata quando si modificano altri campi.
- Viaggi: creazione, elenco, panoramica, prossima tappa, giornate, eventi, prenotazioni, guide con campi temporali riconoscibili, copie offline; periodi e orari complessi conservati come testo libero, modificabili esplicitamente. Nessuna interpretazione automatica di date testuali ambigue o cambio di fuso.
- Diario: date di importazione, anteprima, filtri, eventi e spostamenti; offset locale preservato. Gli algoritmi di importazione, cronologia e ordinamento restano invariati.
- Controlli nativi con configurazione locale italiana, primo giorno lunedì, orologio a 24 ore; temi chiaro/scuro e palette Ocean/Forest/Sunset/Lavender nel Personale. La presentazione usa una funzione dedicata; i valori inviati rimangono ISO.

### Verifiche
- Test unitari Kotlin: ItalianDateTimeTest e WorkFilterTest; test degli altri moduli Android eseguiti dalla CI esistente. Controllo di conversione isolato: 25 asserzioni eseguite sul sorgente identico al blob del commit f7beb05, tutte riuscite. Test API/Web del medesimo commit superati.
- Pipeline APK: assembleDebug, lintDebug, testDebugUnitTest e, per la release firmata, assembleRelease, lintRelease, testReleaseUnitTest e verifica firma. Non dichiarare collaudato prima del risultato.
- Collaudo Samsung (manuale): aggiornare senza disinstallare; verificare calendario italiano e lunedì anche con lingua di sistema diversa, navigazione mesi/anni, temi e palette, annullamento senza cambiamenti, sola data, data/ora, rimozione valori facoltativi, salvataggio/modifica e riscontro web; filtro settimana e ordinamento; viaggio con fuso USA, periodo, orari locali e copia offline; Diario importato; prova notifica professionale, promemoria personale, avviso acustico e background. Nessun test fisico è stato eseguito nell'ambiente di sviluppo.

## Web 0.2.14-test / Android 0.2.9-test — sincronizzazione Viaggi offline
- Implementazione: controllo automatico ogni circa 60 secondi in primo piano e dopo sblocco/ritorno in area Viaggi, solo con autorizzazione personale valida e una copia già scelta dall'utente. Il controllo leggero non trasferisce il ZIP se l'impronta è invariata. Impronta server di revisione, archivio e diario (il diario può cambiare senza revisione).
- Download integrale con identificativo e digest verificati, manifest e riferimenti PDF convalidati, archivio e metadati scritti insieme in un unico file cifrato AES-GCM/Keystore e AtomicFile. Copia legacy migrata alla prima riconsegna riuscita; la precedente resta in caso di errore. La copia aperta non viene sostituita durante la lettura, ma si può riaprire quella aggiornata. Nessun caricamento di dati locali verso il server.
- Un solo viaggio offline, come prima; nessuna sostituzione di un viaggio differente senza conferma. Nessun servizio in background o nuova credenziale; se app bloccata/chiusa non sincronizza. Nessuna modifica alle notifiche.
- Test automatici: fingerprint, sostituzione PDF, modifiche del diario senza incremento revisione, revoca e integrità del ZIP. Collaudo reale ancora necessario: modalità aereo, ritorno rete, sblocco, errore durante download, riapertura PDF, rotazione e aggiornamento APK senza disinstallare. Rollback sorgente: rollback-before-offline-sync; per Android preferire build correttiva con versionCode maggiore, non disinstallare.
- Restano da sviluppare: catalogo tipologie dinamico, assicurazione/emergenze, budget e gestione spazio; non inclusi in questo rilascio.

## Web 0.2.15-test / Android 0.2.10-test — tipologie dinamiche e assicurazione
- Catalogo per account già configurabile sul Web: nuovo endpoint mobile in sola lettura protetto dalla sessione personale; catalogo incluso nel viaggio online e aggiornato all'apertura dell'editor prenotazioni. Icone da elenco consentito, campi specifici modificabili e campi liberi. I ruoli dei luoghi sono visibili; modifica del catalogo e dei luoghi resta sul Web.
- La selezione esplicita di una nuova tipologia salva identificativo, nome e icona del modello; i campi storici, allegati, dettagli, foto e collegamenti non vengono eliminati automaticamente. Modelli rimossi: etichette e campi storici preservati. La revisione del viaggio impedisce sovrascritture concorrenti; modello rimosso durante la modifica produce errore.
- Catalogo incluso solo nelle copie offline Android che lo richiedono; impronta di sincronizzazione include il catalogo. Export ZIP standard, import e vecchie APK mantengono il formato precedente. Nessuna modifica offline ai dati.
- Scheda rapida assicurazione nella panoramica: mostra esclusivamente dati salvati nelle prenotazioni assicurative e relativi PDF, anche offline. Nessun numero di emergenza o contatto inventato.
- Test: isolamento account, validazione campi, conservazione storico e PDF, modifica/rimozione modello, fingerprint e compatibilità ZIP. Collaudo fisico da completare. Backup sorgente rollback-before-dynamic-booking-types. Restano rinvio promemoria, gestione professionale completa, budget e spazio.
