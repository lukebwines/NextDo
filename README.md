# NextDo

NextDo è un'applicazione indipendente da ZEUS e INCA per scadenze, attività e Corsi di Studio, progettata per Home Assistant OS su Raspberry Pi 5 (ARM64).

**Stato: prototipo di sviluppo. Non ancora pronto per installazione produttiva, accesso remoto Cloudflare o utilizzo con dati d'ufficio.**

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
