# NextDo — Home Assistant add-on

**Versione di test: 0.1.4-test.** Dashboard rifinita sulla prima proposta grafica approvata: menu con etichette, quattro contatori cliccabili, aggiunta rapida, scadenze compatte, settimana e riepilogo etichette. Aggiunto il ripristino di archivi ZIP esportati da NextDo.

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
