# Ripristino interfaccia completa dal pacchetto locale 0.1.1

Questo ramo è riservato al ripristino dell'interfaccia e delle funzionalità della versione NextDo-0.1.1-local-test fornita dall'utente. Non deve essere distribuito come aggiornamento finché non siano verificate compatibilità database e autenticazione.

## Differenze accertate

La versione completa usa file separati:
- `nextdo/static/index.html`
- `nextdo/static/style.css`
- `nextdo/static/app.js`
- `nextdo/static/display.html`
- `nextdo/app/main.py`

La versione attualmente sul ramo main usa un diverso schema SQLite:
- utenti: `password` e `role`, contro `password`, `display_name`, `role`, `active` nella versione completa
- gruppi e appartenenze: `membership` contro `memberships`
- task: mancano `kind`, `assigned_to`, `recurrence`, `labels`, `display_enabled`, `updated_at`; la versione completa ha semantica diversa di pubblicazione.
- nomi e caratteristiche dei token display diversi.

## Precauzioni

- Non sostituire direttamente il backend sul main o nel container con dati esistenti senza migrazione.
- Non cancellare né sovrascrivere `/data/nextdo.sqlite3`.
- Fare backup verificato dei dati attualmente presenti; non pubblicarlo sul repository.
- Sviluppare e collaudare una migrazione transazionale, reversibile su backup.
- Mantenere codici e denominazioni CdS esclusivamente locali.
- Dopo validazione, rilasciare una versione superiore a quella installata, anziché riusare `0.1.1-test`.

Il repository pubblico deve contenere esclusivamente codice e dati fittizi nei test.

## Collaudo del pacchetto completo 0.1.3-test

L'archivio aggiornato dalla versione locale comprende i moduli originali, interfaccia CSS/JS, backend FastAPI, Ingress e una migrazione dello schema semplificato del repository.

Verifiche locali superate: creazione amministratore con codice monouso, login, creazione task, estrazione testo, migrazione da schema precedente, conservazione task e gruppi, accesso successivo alla migrazione, controllo sintattico Python e JavaScript.

Il pacchetto completo risiede nell'allegato della conversazione e **non è ancora stato importato in questo ramo GitHub**. Sono ancora da verificare build ARM64 sul Raspberry e corretta installazione nel Supervisor.
