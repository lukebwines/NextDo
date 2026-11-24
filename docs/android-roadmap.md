# NextDo Android — roadmap prioritaria

## Obiettivo
Un'unica app NextDo, con dashboard generale e due aree separate, come sul web. Viaggi rimane un modulo personale; nessuna perdita di dati o funzioni esistenti. L'identificativo uk.archis.nextdoviaggi, la firma APK, i tag android-v e gli asset nextdo-viaggi.apk/json restano invariati per compatibilità.

| Versione Android indicativa | Obiettivo | Stato |
| --- | --- | --- |
| 0.1.7-test | Nuovo nome e icona; dashboard, Professionale, Personale, Impostazioni, navigazione modulare; Viaggi integro | Integrata, CI superata |
| 0.1.8-test | Associazione professionale esplicita, API dedicate e minimali, agenda settimanale, scadenze e appuntamenti anche da verificare, arretrati, priorità | Implementata, test richiesti |
| 0.1.9-test | Notifiche push e locali, canali di priorità, avvisi urgenti ripetuti fino alla presa visione, preferenze e permessi Android | Da sviluppare |
| 0.1.10-test | Presa visione, rinvio, completamento e aggiornamento coerente con il web | Da sviluppare |
| 0.1.11-test | Agenda, note e promemoria personali con accesso separato | Da sviluppare |
| Successive | Ripresa roadmap Viaggi | Sospesa |

## Sicurezza e vincoli
- Nessuna estensione automatica dei token Viaggi. Autorizzazione professionale specifica, revocabile e limitata ai dati effettivamente accessibili dall'utente sul web. Non esporre API amministrative, cookie web, credenziali o database.
- Dati professionali e personali distinti anche in eventuali cache, notifiche e log. Nessun dettaglio sensibile nelle notifiche sullo schermo bloccato per impostazione predefinita. Non includere dati privati o professionali nel repository.
- Il Raspberry resta fonte autorevole: includere le voci da verificare, non confondere mancanza di connessione con agenda vuota. Fuso orario, deduplicazione e aggiornamenti da verificare.
- Notifiche realmente funzionanti ad app chiusa richiedono una strategia push e promemoria locali da progettare. Avvisi ripetuti, suoni prolungati e modalità allarme dipendono dai permessi, dalle regole Android e dal risparmio energetico. Non promettere aggiramento delle impostazioni di sistema.
- Prima del rilascio test di regressione Viaggi, firma permanente, aggiornamento senza disinstallazione, collaudo Samsung. La 0.1.7-test non attiva ancora API professionali o notifiche.

Numerazioni indicative; priorità: completare l'area professionale e gli avvisi prima di riprendere gli sviluppi Viaggi.

## Agenda professionale — server 0.1.39-test / Android 0.1.8-test
Pairing dedicato nella Dashboard web (codice 5 minuti, token revocabile 30 giorni, hash lato server e Keystore Android); nessuna credenziale Viaggi può accedere all'agenda. Password cambiata, account disattivato/cancellato e restore invalidano l'accesso. Le voci scope personal del gestionale web sono attività lavorative private, incluse perché anche le email da verificare usano tale scope; esclusi note e Viaggi. Agenda aperta paginata in sola lettura, dettagli su richiesta, timezone server, senza orario inventato, filtri settimana/urgenti/scadute/trascorsi/da verificare/senza data/tutte. Refresh all'apertura Home/Lavoro e manuale; nessuna sincronizzazione in background, cache professionale persistente o notifica ancora. Collaudare gateway HTTPS per /api/mobile/v1/work/, associazioni distinte, revoca e aggiornamento APK.
