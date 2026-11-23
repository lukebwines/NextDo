# Gmail automatico → Scadenze NextDo

## Cosa fa

Dopo una configurazione iniziale, l'amministratore può inoltrare manualmente i messaggi ritenuti pertinenti a `luca.belduvini+nextdo@gmail.com`. Il filtro Gmail già configurato applica l'etichetta **NextDo**. NextDo, tramite le API Gmail e Google OAuth, controlla ogni 5 minuti **solo i messaggi etichettati NextDo**. Non legge gli allegati, non modifica i messaggi e non usa integrazioni Microsoft 365.

Solo le email ricevute **dopo l'attivazione** sono importabili automaticamente. Per ciascuna email pertinente NextDo invia a GroqCloud il testo necessario all'estrazione; le proposte sono salvate come attività **Da verificare**, private dell'amministratore, non assegnate a colleghi o CdS, senza promemoria automatici. Se la data è presente in modo inequivocabile viene registrato soltanto il giorno, senza inventare un orario; per le altre scadenze resta senza data. Una scadenza da verificare non può essere completata senza essere prima confermata. Per la conferma, aprire la scadenza, verificare fonte e dati, impostare **Da fare** e salvare.

Un registro persistente conserva ID Gmail, esito del tentativo, numero di attività create e motivi sintetici degli errori. Ogni attività conserva ID del messaggio, oggetto, mittente, frase originale e impronta del contenuto. La deduplicazione opera su ID Gmail, impronta del testo e impronta delle singole proposte. Le email non vengono archiviate integralmente nel database NextDo.

## Configurazione Google (una tantum)

1. Aprire [Google Cloud Console](https://console.cloud.google.com/) e creare o selezionare un progetto controllato dall'utente.
2. Abilitare la **Gmail API** per il progetto.
3. Configurare la **schermata consenso OAuth**, aggiungere l'account Gmail come utente di test se l'app è in modalità Test, e richiedere lo scope `https://www.googleapis.com/auth/gmail.readonly`.
4. Creare un **ID client OAuth → Applicazione web**.
5. Registrare tra gli URI di reindirizzamento autorizzati l'indirizzo HTTPS esattamente uguale a quello mostrato in **NextDo → Impostazioni → Gmail → scadenze automatiche**, ad esempio `https://nextdo.archis.uk/api/gmail-auto/callback`.
6. Copiare **Client ID** e **Client Secret** nella sezione NextDo, lasciare disattivato il controllo e premere **Salva impostazioni Gmail**.
7. Selezionare **Collega Google**, concedere il permesso richiesto ed attendere il ritorno a NextDo.
8. In **Impostazioni**, spuntare **Abilita acquisizione automatica** e salvare. Per provare senza attendere 5 minuti, inoltrare un nuovo messaggio sintetico e premere **Controlla adesso**.

L'app chiede il permesso Gmail `gmail.readonly`, che tecnicamente consente l'accesso in sola lettura **all'intera casella**, anche se NextDo elabora esclusivamente l'etichetta NextDo. L'utilizzo dello scope Gmail può essere soggetto alle procedure di verifica Google. Gli account OAuth in modalità Test possono avere token di rinnovo a scadenza ravvicinata e richiedere un nuovo collegamento.

## Sicurezza, backup e limiti

- Non viene richiesta né salvata la password principale di Gmail. I token OAuth e il segreto del client sono cifrati in `/data/gmail-auto-local.json` tramite la chiave locale `/data/email-intake.key`; la stessa chiave protegge la chiave API GroqCloud. Chi accede all'installazione e alla chiave locale potrebbe comunque utilizzarla per accedere ai dati.
- Il **backup Home Assistant dell'add-on**, includendo la cartella dati, è necessario per ripristinare configurazione e chiave. L'esportazione ZIP applicativa NextDo conserva database e allegati, **non** le credenziali OAuth o i file di configurazione: dopo il suo ripristino il collegamento Gmail va riconfigurato.
- NextDo non rimuove l'etichetta, non contrassegna i messaggi come letti e non esegue operazioni di scrittura in Gmail.
- Le richieste Google e GroqCloud richiedono connessione Internet. Gli errori per singolo messaggio sono registrati senza password, token o corpi completi delle risposte Google.
- Il controllo automatico è limitato a una installazione NextDo avviata e raggiungibile; se è spenta, riprende al successivo avvio. Gli errori temporanei sono ritentati; il numero di tentativi è limitato.
- Non inoltrare email istituzionali o dati personali verso caselle e provider esterni senza aver verificato autorizzazioni e condizioni di trattamento dei dati.

**Non sono richieste credenziali Gmail o GroqCloud in chat o in un repository pubblico.**
