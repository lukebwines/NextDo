# NextDo — Android test

App nativa Kotlin / Jetpack Compose (Android 11 o superiore). Prima versione in sola lettura, con PDF integrati e una copia offline cifrata del viaggio selezionato.

## Connessione
1. Aggiorna NextDo alla versione server che comprende le API mobile.
2. Apri Area personale → Viaggi → App Android, genera un codice monouso (5 minuti).
3. Sul telefono sblocca l'app con la credenziale Android, inserisci URL HTTPS diretto NextDo e codice. Il token dispositivo dura 30 giorni; il PIN NextDo sblocca le API di lettura per 5 minuti.
4. Seleziona un viaggio. Per l'uso offline scarica esplicitamente il pacchetto; puoi aprirlo senza rete dal menu iniziale dopo lo sblocco Android.
5. Per revocare il telefono, usa App Android nell'interfaccia web. Revoca online non elimina una copia già scaricata; cancellala sul telefono. L'app si blocca quando passa in background.

Serve un endpoint HTTPS realmente accessibile dal telefono, ad esempio mediante un gateway/VPN configurato appositamente. Il percorso ingress Home Assistant dipende dalla sessione HA e non è un endpoint mobile autonomo. Non disabilitare la verifica TLS. L'APK di CI è una build debug di collaudo, non firmata per produzione; un APK successivo può avere una firma debug differente e richiedere disinstallazione. Conservare i dati autorevoli sul server.

## Build
Gradle 8.9, JDK 17, Android SDK 35:
    gradle -p android :app:assembleDebug :app:lintDebug

GitHub Actions: Android Viaggi APK. Artifact NextDo-Viaggi-Android-test. I test server usano solo dati sintetici. Collaudare associazione, accesso dall'esterno, PDF e offline su un vero dispositivo prima di affidarsi all'app in viaggio.

## Limiti della prima versione
Niente modifiche alle prenotazioni/checklist sul server, promemoria push, AI o sincronizzazione in background. La copia offline è un'istantanea, non si aggiorna automaticamente. Non è inclusa un'app Play Store o una configurazione automatica del tunnel remoto.

## Sblocco biometrico (0.1.1-test)
Prompt biometrico di sistema Android con biometria forte (impronta se disponibile) oppure PIN, password o sequenza del telefono. Nessuna impronta acquisita dall’app. Blocco in background e dopo 5 minuti dallo sblocco. Il PIN NextDo resta obbligatorio per la sessione server. Collaudare impronta, annullamento, fallback e offline sul dispositivo reale. Non richiede un aggiornamento server ulteriore rispetto a 0.1.34-test.

## Accesso ricordato (Android 0.1.3-test / server 0.1.35-test)
Il primo PIN NextDo rilascia un segreto casuale dedicato al dispositivo, cifrato con il Keystore Android e conservato sul server solo come hash. Non viene conservato il PIN. Lo sblocco locale tenta automaticamente una nuova sessione di lettura di 5 minuti. Il segreto scade al massimo dopo 30 giorni e non oltre l'associazione; la revoca elimina le sessioni e il segreto. In caso di mancata connessione l'archivio offline resta disponibile. La riassociazione o un nuovo PIN possono essere necessari alla scadenza. Test fisico e HTTPS richiesti.

## Distribuzione con firma stabile
Vedi [Configurazione firma e release Android](SIGNING.md). L'app verifica le release Android pubbliche all'avvio o su richiesta; controlla SHA-256, nome pacchetto, versione e firma prima di passare al programma di installazione Android. Nessun token GitHub o dato dei viaggi viene inviato. Le build debug non sono aggiornabili con una firma di produzione differente; il primo passaggio alla firma stabile richiede una reinstallazione, con nuova associazione e download offline. I dati centrali restano sul Raspberry. Il codice server 0.1.35-test non cambia.

## Modifiche online (0.1.5-test / server 0.1.36-test)
Import ZIP dal selettore Android con conferma, creazione viaggio con date, modifica titolo/sottotitolo, giornate, eventi e dati principali prenotazioni; aggiunta eventi e prenotazioni. I PDF, i campi avanzati, le foto e i riferimenti esistenti restano intatti. Le modifiche richiedono Internet; su conflitto annullare e riaprire il viaggio. La copia offline resta un'istantanea da riscaricare. Date di viaggi esistenti, allegati, eliminazioni e campi avanzati non sono modificabili da questa prima interfaccia. Il selettore documenti può richiedere un nuovo sblocco al ritorno.

## Diario di bordo (0.1.5-test / server 0.1.36-test)
Vedi [Diario di bordo](../docs/travel-timeline.md). Import JSON con filtro locale, anteprima e conferma; visualizzazione del tracciato schematico e statistiche sul web. Nessun GPS autonomo. Collaudo del formato reale del Samsung necessario. Il diario non è incluso nel pacchetto offline o nello ZIP.

## Diario consultabile (0.1.6-test / server 0.1.37-test)
Visualizzazione e filtro giorno, confronto tappe geolocalizzate e tracce effettive, zoom/pan, sfondo cartografico opzionale (richiesta esplicita), statistiche e note. Il download offline include il diario; sfondo esterno disponibile solo online. Il backup ZIP con diario si esporta dal web; la normale importazione Android ripristina anche timeline.json, senza duplicati. Collaudo reale necessario.

## App modulare (Android 0.1.7-test)
Nome pubblico NextDo, icona e dashboard generale, aree Professionale e Personale separate, Impostazioni e Viaggi come modulo. Il blocco biometrico e l'identificativo pacchetto, firma, credenziali Viaggi e archivi cifrati restano invariati. L'area professionale è per ora una struttura non collegata, senza dati simulati né accesso ai dati professionali. Notifiche e moduli personali non Viaggi non sono ancora attivi. Non richiede migrazioni o aggiornamento server aggiuntivo. Vedi [roadmap Android](../docs/android-roadmap.md).

## Agenda professionale (0.1.8-test / server 0.1.39-test)
Dalla Dashboard web: NextDo Android · Professionale → Genera codice; Android → Lavoro → URL HTTPS e codice. Associazione distinta da Viaggi, revocabile, sola lettura. Nessuna password in app. Agenda con tutte le voci aperte accessibili, incluse Da verificare e senza data. Aggiornamento quando si apre Home/Lavoro e manuale; niente notifiche o background in questa versione. Se si cambia password o scade l'associazione, revocare e associare nuovamente. Il gateway deve consentire solo le API mobile dedicate.

## Notifiche professionali (0.1.9-test / server 0.1.40-test)
Impostazioni → Notifiche professionali: concedi permessi, attiva, prova avviso critico. WorkManager interroga il server ogni 15 minuti circa e usa promemoria locali non esatti. Priorità bassa/silenziosa, normale, alta, critica; critici ripetuti fino a presa visione locale con intervallo 15/30/60 minuti. Suoni e vibrazioni dipendono dai canali Android; i dati di dettaglio non sono inviati al servizio background. Metadati cifrati temporanei (24 ore dall'ultimo sync). Non è push in tempo reale; Android può ritardare gli avvisi. Disattivazione e revoca separate da Viaggi. Non considerare il sistema collaudato prima dei test sul Samsung.
