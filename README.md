# NextDo

NextDo è un'applicazione indipendente da ZEUS e INCA per scadenze, attività e Corsi di Studio, progettata per Home Assistant OS su Raspberry Pi 5 (ARM64).

**Stato: v0.1.1-test, solo collaudo locale tramite Ingress Home Assistant. NON pronto per produzione, Cloudflare o dati d'ufficio.**

## Riservatezza dei CdS

Il repository non contiene e non deve contenere alcun elenco, codice reale o denominazione dei Corsi di Studio. L'anagrafica parte vuota e viene inserita **solo sull'installazione locale** dall'amministratore. Il database viene conservato in `/data/nextdo.sqlite3` nel container add-on, non nel codice.

Non committare dati locali, backup, allegati, credenziali o esportazioni. Il file `.gitignore` riduce il rischio di caricamenti accidentali, ma non sostituisce il controllo prima di ogni commit.

## Codice disponibile

- `nextdo/app/main.py`: backend FastAPI con installazione iniziale dell'amministratore, login, sessioni, gruppi, CdS locali, scadenze collegate a più corsi e completamento globale/per corso
- `nextdo/static/index.html`: prima dashboard responsive con grafica blu notte / azzurro, inserimento locale dei CdS e delle attività
- `nextdo/config.yaml`, `nextdo/Dockerfile`, `nextdo/run.sh`: struttura add-on Home Assistant
- `tests/test_api.py`: test API con sole stringhe fittizie, senza codici e nomi di CdS
- `.github/workflows/tests.yml`: test automatici sulle modifiche

Il motore di estrazione fornisce una **proposta da confermare**; non salva automaticamente attività dal testo copiato. Il monitor mostra soltanto titoli, date, stati e priorità autorizzati dal flag di pubblicazione in un gruppo.

## Avvio per sviluppatori

Eseguire **in ambiente di test isolato**, non accessibile via Internet:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r nextdo/requirements.txt
export NEXTDO_DATA=./local_data
PYTHONPATH=nextdo uvicorn app.main:app --host 127.0.0.1 --port 8095
```

Aprire `http://127.0.0.1:8095`. Per i test: `PYTHONPATH=nextdo pytest -q tests` dopo l'installazione di `pytest` e `httpx`.

## Da completare prima del rilascio

Gestione estesa degli utenti e dei gruppi dall'interfaccia, note libere strutturate, allegati, ricorrenze automatiche, notifiche, import CSV e backup/ripristino; gestione sicura dei token Display; revisione completa dell'autorizzazione alle modifiche; collaudo effettivo del build ARM64 e del funzionamento su Home Assistant OS; configurazione HTTPS / Cloudflare Tunnel e sicurezza.

**Non aggiungere questo repository agli add-on di Home Assistant fino al completamento del collaudo.** Il file di configurazione dell'add-on è provvisorio, e la porta 8095 deve restare nell'ambiente di test.


## Protezione v0.1.1-test

- Ingress di Home Assistant abilitato, nessuna porta pubblicata sull'host.
- Primo amministratore protetto da codice monouso generato nell'add-on e visibile nei suoi log di avvio; il codice NON è incluso in GitHub.
- Se l'installazione non è stata configurata, leggere il codice nei log del container e inserirlo nella schermata iniziale di NextDo.
- Il token di configurazione viene eliminato una volta creato il primo amministratore.
- I dati CdS sono esclusivamente locali in `/data`.
- Nessun Cloudflare Tunnel o accesso diretto per i colleghi deve essere configurato durante questa fase.

### Repository pubblico e aggiornamenti

Il repository è pubblico e può essere consultato senza credenziali. Non contiene anagrafiche CdS, database, note o credenziali reali. **Non utilizzare ancora il repository per aggiornare un'installazione NextDo esistente**: la versione GitHub `0.1.1-test` non è stata allineata e verificata rispetto a eventuali versioni locali più recenti. Prima di adottare gli aggiornamenti tramite Home Assistant occorre controllare versione, slug, persistenza di `/data` e migrazioni, e verificare la compilazione ARM64. In particolare, non disinstallare l'installazione esistente e non eliminare i suoi dati.

L'uso di GitHub come sorgente di installazione non pubblica automaticamente il database persistente dell'add-on.

Prima dell'installazione sul Raspberry sono ancora richiesti la verifica dei test CI e un collaudo della build ARM64. Non avviare su rete esterna e non inserire dati reali fino al completamento del collaudo.
