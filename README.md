# NextDo — Home Assistant add-on

**Versione di test: 0.1.3-test.** Ripristinata la dashboard completa della versione locale originale (note, scadenze, calendario, gruppi, archivio, etichette, allegati e monitor).

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
