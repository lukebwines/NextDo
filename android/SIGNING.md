# Firma permanente e pubblicazione Android

La chiave privata non deve essere pubblicata, inviata per email o inserita nel repository.
Generarla una sola volta su un PC fidato. Occorrono Java JDK 17 (keytool) e un account
GitHub con accesso alle impostazioni del repository.

## 1. Genera la chiave
In PowerShell, in una cartella privata non sincronizzata con Git:
    keytool -genkeypair -v -storetype PKCS12 -keystore nextdo-viaggi.p12 -alias nextdo-viaggi -keyalg RSA -keysize 3072 -validity 10000 -dname "CN=NextDo Viaggi"
Scegli una password lunga e unica. PKCS12 usa la stessa password per chiave e archivio.
Conserva due copie di backup sicure dell'archivio e la password separatamente.
Non rigenerare la chiave dopo la prima release: Android non accetterebbe gli aggiornamenti.

## 2. Configura GitHub Secrets
Apri https://github.com/lukebwines/NextDo/settings/secrets/actions .
Crea due Repository secrets (New repository secret):
- ANDROID_KEYSTORE_B64: valore Base64 del file .p12, non il nome del file.
  Da PowerShell, dalla cartella contenente il file, copialo direttamente negli appunti:
      [Convert]::ToBase64String([IO.File]::ReadAllBytes((Resolve-Path '.\nextdo-viaggi.p12').Path)) | Set-Clipboard
  Incollalo nel campo Secret, salva e svuota gli appunti con Set-Clipboard -Value ''.
- ANDROID_KEYSTORE_PASSWORD: la password del file .p12.
Non incollare questi valori in chat. Non inserirli in un file di testo nel repository.

## 3. Prima release
In Actions seleziona Android Viaggi — release firmata, Run workflow, branch main,
inserisci le note della versione e avvia. Il workflow compila la variante release,
firma con la chiave stabile, verifica l'APK, pubblica nextdo-viaggi.apk e
nextdo-viaggi.json in una release android-v<versione>. Non sovrascrive tag esistenti.
Le build pull request rimangono debug e non usano questi secrets.
Prima dell'installazione verificare che il workflow sia terminato con successo.

## 4. Installazione e aggiornamenti
Per il primo passaggio da debug a firma stabile, conservare i dati centrali sul
Raspberry. Disinstallare la precedente app debug solo quando la release firmata
è disponibile; ciò elimina associazione e copia offline locali. Installare il
nuovo APK pubblico, associare nuovamente il dispositivo e scaricare i documenti.
Le successive release con stessa firma e versionCode crescente si installano
sopra l'app esistente. Lo smartphone richiede conferma esplicita e, al primo
aggiornamento dall'app, l'autorizzazione Android a installare app da questa fonte.
La verifica SHA-256, del pacchetto, della versione e della firma precede
l'apertura dell'installatore di sistema. Nessun aggiornamento silenzioso.
