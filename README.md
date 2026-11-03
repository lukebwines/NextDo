# NextDo

Gestione indipendente di attività, note, scadenze e Corsi di Studio per Home Assistant OS.

## Riservatezza CdS

**Nessun codice o nome reale di Corso di Studio deve essere inserito in questo repository.** Le anagrafiche sono caricate esclusivamente nell'installazione locale da un amministratore, tramite modulo o importazione CSV, e salvate nel database persistente del dispositivo.

Non caricare mai file di esportazione, backup, allegati, database, dati degli utenti, password o token. Il file `.gitignore` esclude i principali formati dati per ridurre il rischio di pubblicazione accidentale; per ulteriori precauzioni sono necessari controlli prima di ogni commit.

## Architettura prevista

- App indipendente da ZEUS e INCA, per Raspberry Pi 5 / Home Assistant OS.
- Account NextDo, gruppi di lavoro, attività private e condivise.
- Note, priorità, calendario, ricorrenze e allegati.
- Associazione multipla delle scadenze ai CdS e completamento globale o per CdS.
- NextDo Display per scadenze esplicitamente pubblicate.
- UI dark blu notte e azzurro, con modalità chiara.

## Stato

Repository di preparazione: il codice applicativo completo non è ancora stato caricato da questo ambiente. Il prototipo di test v0.1.0 è disponibile come archivio nella conversazione ChatGPT che ha originato questo progetto. Non installare o esporre su Internet finché codice, test e sicurezza non sono stati verificati.

## Distribuzione

Installare solo dopo il completamento del codice e dei test sul Supervisor Home Assistant. Il servizio deve rimanere privato finché non siano stati collaudati accessi multiutente, backup, permessi e tunnel HTTPS.
