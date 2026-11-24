# NextDo: ricezione diretta delle email con Cloudflare

## Obiettivo

Inoltrare **manualmente e in modo selettivo** le email pertinenti a una casella dedicata Cloudflare, senza Gmail, OAuth Google o server SMTP sul Raspberry. Un Worker Cloudflare verifica il mittente e consegna il MIME a NextDo tramite un endpoint HTTPS con firma HMAC SHA-256.

NextDo mette in coda il testo in forma cifrata, scarta gli allegati, invia a GroqCloud le parti testuali necessarie, evita duplicati e crea scadenze private dell'Admin in stato **Da verificare**. Le date non certe restano da acquisire; nessun collega o CdS viene attribuito automaticamente.

## 1. Preparare l'indirizzo di ricezione

È necessario che la zona DNS sia gestita in Cloudflare.

**Importante:** se il sito NextDo usa un record CNAME sul nome nextdo.archis.uk (come è comune con Cloudflare Tunnel), non attivare la posta sullo stesso nome, perché MX e CNAME possono entrare in conflitto. Utilizzare un sottodominio separato e inutilizzato, per esempio **posta.archis.uk**. I nomi indicati qui sono soltanto esempi, non indirizzi già attivi.

Nel pannello Cloudflare aprire **Compute → Email Service → Email Routing**, selezionare il dominio e, in **Settings → Subdomains**, abilitare il sottodominio scelto. Attendere la predisposizione dei record MX richiesti da Cloudflare.

Creare poi una regola per un **indirizzo esatto** sul sottodominio, per esempio scadenze@posta.archis.uk, scegliendo come destinazione **Send to a Worker**. Non usare regole catch-all che potrebbero inoltrare messaggi indesiderati.

Documentazione ufficiale:
- https://developers.cloudflare.com/email-service/configuration/subdomains/
- https://developers.cloudflare.com/email-service/configuration/email-routing-addresses/

## 2. Creare il Worker

In Cloudflare aprire **Workers & Pages → Create Worker**, creare un Worker e utilizzare il contenuto di [cloudflare/nextdo-email-worker.js](../cloudflare/nextdo-email-worker.js).

Configurare le variabili di testo:

| Variabile | Valore |
|---|---|
| NEXTDO_ENDPOINT | URL HTTPS pubblico di NextDo seguito da /api/cloudflare-mail/inbound |
| EXPECTED_TO | Indirizzo completo creato per la ricezione, senza indirizzi aggiuntivi |
| ALLOWED_FROM | Indirizzi esatti dai quali si effettuano gli inoltri, separati da virgole |

Configurare una **variabile segreta**, senza scriverne il valore nel repository:

| Variabile segreta | Valore |
|---|---|
| NEXTDO_SIGNING_SECRET | Segreto generato in NextDo → Impostazioni → Posta in arrivo Cloudflare |

Il controllo del mittente funziona sull'indirizzo **SMTP envelope sender** (non necessariamente il From mostrato nell'email). Verificare il comportamento dell'inoltro nella prova iniziale. Cloudflare applica controlli di autenticazione ai messaggi entranti, ma il filtro mittente non è da solo un'autenticazione dell'utente.

Se l'hostname NextDo è protetto da **Cloudflare Access**, creare un **Service Token** e una regola Access di tipo **Service Auth** che ne consenta l'utilizzo. Configurare le ulteriori variabili segrete **CF_ACCESS_CLIENT_ID** e **CF_ACCESS_CLIENT_SECRET** sul Worker. Limitare la regola Access al percorso dell'endpoint quando possibile.

Documentazione:
- https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/

Infine creare la regola **Email Routing → Send to a Worker** che associa l'indirizzo esatto al Worker.

## 3. Configurare NextDo

1. Installare la versione di NextDo che include la funzione Cloudflare.
2. Aprire **Impostazioni → Posta in arrivo Cloudflare → Scadenze**.
3. Inserire il destinatario configurato in Cloudflare e gli stessi mittenti autorizzati del Worker, separati da virgole.
4. Fare clic su **Genera / rigenera segreto Worker**, copiare il valore una sola volta, inserirlo come segreto del Worker e verificare che i valori dei due lati coincidano.
5. Salvare le impostazioni e attivare **Abilita la ricezione automatica**.
6. Inviare un messaggio sintetico, senza dati personali o informazioni istituzionali riservate, dal mittente configurato. Controllare il registro email e poi le **Scadenze → Da verificare**.
7. Per confermare un'attività, aprirla, verificare la fonte, impostare lo stato **Da fare** e salvarla. Non è consentito completare direttamente una scadenza non verificata.

## Sicurezza e comportamento

- NextDo accetta esclusivamente richieste firmate con HMAC SHA-256, timestamp valido (5 minuti), destinatario e mittente esatti. Una richiesta duplicata viene riconosciuta anche dopo il riavvio.
- Il Worker invia il MIME in HTTPS. La coda salva **solo il testo analizzabile**, in forma cifrata con la chiave locale di NextDo; dopo l'elaborazione il testo in coda viene cancellato, conservando identificativi e provenienza nella scheda e nel registro.
- Il database conserva la traccia dei messaggi, gli stati e le impronte per la deduplicazione. Lo stesso messaggio o contenuto non genera ulteriori attività già registrate. La gestione degli errori effettua fino a tre tentativi.
- Il controllo della coda avviene ogni circa 10 secondi, con servizio avviato; il Worker non deve attendere l'elaborazione di GroqCloud per confermare la ricezione.
- Non sono necessari account Gmail né servizi Microsoft 365. Il server NextDo **non espone un server SMTP**.
- L'email non viene copiata integralmente nell'archivio NextDo dopo l'elaborazione; conservare gli originali nel sistema di posta di provenienza.
- I file di configurazione cifrati e la chiave di cifratura locale devono essere inclusi nel **backup Home Assistant dell'add-on**. L'esportazione ZIP applicativa di NextDo include database e allegati ma non tutti i segreti locali.
- In assenza di firma valida, Cloudflare Access o connessione HTTPS, il Worker non riceve l'ack HTTP 202 e il messaggio potrebbe non essere recapitato. Consultare i log Cloudflare e non presumere la consegna.
- L'automazione rimane **disattivata** fino alla configurazione e all'attivazione esplicita dall'interfaccia Admin.
- Per messaggi istituzionali, valutare autorizzazione all'inoltro su domini esterni, trattamento dei dati da parte di Cloudflare e GroqCloud e limiti di conservazione prima dell'utilizzo reale.
