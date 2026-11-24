# NextDo Viaggi — roadmap

## Principi

- Un motore universale per viaggi futuri, configurabile dall'interfaccia: nessun itinerario o dato personale nel repository.
- NextDo sul Raspberry rimane la fonte autorevole dei dati; area personale separata dall'ambiente professionale.
- Compatibilità con archivi ZIP e viaggi esistenti; migrazioni additive e test di regressione.
- Servizi esterni configurati per account: GroqCloud per testo, Geoapify per geografia; fotografie esclusivamente caricate manualmente.
- Rilasci incrementali con test; numeri sotto indicativi, non promesse di consegna.

## Roadmap

| Versione indicativa | Obiettivo | Funzioni |
| --- | --- | --- |
| 0.1.33-test (rilasciata) | Motore universale | Tipologie prenotazione, più luoghi, campi personalizzati, percorsi giornalieri Geoapify |
| 0.1.34 | Inbox Viaggi | Ricezione su indirizzo dedicato, separazione dalla posta professionale, allegati privati, proposte GroqCloud, associazione viaggio, deduplicazione, conferma modifiche e tracciabilità |
| 0.1.35 | Modalità viaggio | Dashboard mobile Oggi, documenti e navigazione rapidi, promemoria privati con fusi orari, check-in, cancellazioni e riconsegne |
| 0.1.36 | Geografia e contesto | Mappa interattiva, itinerari e POI, meteo con fonte e aggiornamento, indicazioni e stime |
| 0.1.37 | Assistente e guide | Q&A sul viaggio selezionato, guide con fonti e date verificabili, suggerimenti da confermare |
| 0.1.38 | Gestione avanzata | Budget multivaluta, documenti offline, modelli riutilizzabili senza dati del viaggio precedente |
| 1.0.0 | Stabilizzazione | Collaudo complessivo, sicurezza, backup/restore, accessibilità, prestazioni e compatibilità |

Priorità operativa: modalità viaggio, documenti offline e acquisizione prenotazioni. Il versionamento può essere riordinato in funzione dei collaudi.

Ulteriori evoluzioni: esportazione ICS, diario fotografico, condivisione selettiva, riepilogo PDF. Non ancora implementate.

## NextDo Viaggi per Android (proposta di sviluppo)

App companion dedicata esclusivamente a Area personale → Viaggi, senza accesso alle attività professionali. Kotlin e Jetpack Compose come soluzione nativa proposta; API HTTPS versionate sul server NextDo. Il progetto Android può risiedere in una cartella android/ dello stesso repository, con build CI e APK di test firmato prima della distribuzione. Nessuna chiave privata o credenziale nel repository.

### A — Connessione e autenticazione

- URL server configurabile; accesso remoto tramite rete privata/VPN o gateway HTTPS autenticato. L'ingress Home Assistant attuale non è, da solo, un endpoint mobile pubblico.
- Pairing esplicito del dispositivo con account NextDo e autorizzazione specifica Viaggi; token revocabili, scadenza, rotazione e limitazione tentativi.
- Verifica lato server dell'account, del dispositivo e del blocco area personale. PIN/biometria locale per riaprire l'app; Android Keystore per proteggere le credenziali. Nessun bypass del PIN server.
- Verifica TLS e nessun collegamento non cifrato su Internet; non esporre il database, le credenziali Home Assistant o le API amministrative.
- Le chiavi GroqCloud/Geoapify restano sul server, mai nel client.

### B — Prima app utilizzabile

- Selezione viaggio, copertina, countdown e modalità Oggi.
- Timeline, prenotazioni, guide, checklist e note, navigazione tramite app mappe, visualizzazione voucher e PDF.
- Sincronizzazione con API dedicate, revisioni e gestione esplicita dei conflitti. Prima versione eventualmente in sola lettura per i dati principali; modifiche abilitate dopo collaudo.
- Nessuna importazione obbligatoria di un secondo archivio e nessuna duplicazione manuale dei dati.

### C — Offline e notifiche

- Download esplicito del viaggio e dei documenti selezionati per uso offline; archivio locale protetto, blocco locale e cancellazione dati al logout/rimozione pacchetto.
- Indicatori di ultimo aggiornamento e stato offline; eventuali note/checklist offline accodate e riconciliate senza sovrascrivere modifiche concorrenti.
- Promemoria locali pianificati con fuso orario e permessi Android, aggiornabili dopo la sincronizzazione. Notifiche senza dati sensibili sulla schermata di blocco come impostazione predefinita.
- Test in modalità aereo, revoca dispositivi (effettiva al successivo contatto server; offline protetto localmente), cambio fuso, ripristino, perdita connessione.

### D — Evoluzione

- Acquisizione da condivisione Android di PDF/email con conferma, spese e ricevute, ricerca POI/meteo, assistente AI.
- Distribuzione iniziale APK di test, poi valutazione Play Store. Firma APK persistente custodita fuori da Git.
- Prima del rilascio: collaudo remoto reale, test su smartphone e verifica privacy/offline.

## Aggiornamento priorità — Android

Dopo il collaudo della firma permanente (Android 0.1.4-test / server 0.1.35-test), il prossimo rilascio accorpa le tre funzioni richieste: import ZIP originale, creazione nuovo viaggio e modifica online di dati del viaggio, giornate, eventi e prenotazioni. Controllo revisioni, niente sovrascrittura di un ZIP duplicato. L'inbox email resta alla fase successiva. Nessun cambio di formato. Rilascio proposto server 0.1.36-test / Android 0.1.5-test, subordinato ai test.
