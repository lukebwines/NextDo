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
