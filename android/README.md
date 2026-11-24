# NextDo Viaggi — Android test

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

## Accesso solo con codice (0.1.2-test)
Il client non richiede permessi biometrici né usa BiometricPrompt. Usa la conferma del codice di blocco Android (PIN/password/sequenza), mantenendo il PIN NextDo sul server. Nuove chiavi Keystore richiedono esclusivamente la credenziale dispositivo; le chiavi create dalle precedenti versioni sono mantenute per non perdere la copia offline e restano utilizzabili dopo la conferma del codice. Il blocco automatico dopo 5 minuti e in background rimane attivo. Verificare sul dispositivo reale il codice, l'annullamento e l'accesso offline. Server 0.1.34-test invariato.
