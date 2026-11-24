# NextDo Android — roadmap prioritaria

## Obiettivo
Un'unica app NextDo, con dashboard generale e due aree separate, come sul web. Viaggi rimane un modulo personale; nessuna perdita di dati o funzioni esistenti. L'identificativo uk.archis.nextdoviaggi, la firma APK, i tag android-v e gli asset nextdo-viaggi.apk/json restano invariati per compatibilità.

| Versione Android indicativa | Obiettivo | Stato |
| --- | --- | --- |
| 0.1.7-test | Nuovo nome e icona; dashboard, Professionale, Personale, Impostazioni, navigazione modulare; Viaggi integro | Integrata, CI superata |
| 0.1.8-test | Associazione professionale esplicita, API dedicate e minimali, agenda settimanale, scadenze e appuntamenti anche da verificare, arretrati, priorità | Integrata, CI superata |
| 0.1.9-test | Avvisi in background e locali, canali di priorità, ripetizione critica e presa visione locale, preferenze e permessi Android | Implementata, CI e collaudo richiesti; push istantaneo da sviluppare |
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

## Avvisi professionali — server 0.1.40-test / Android 0.1.9-test
Opt-in in Impostazioni dopo pairing e permesso Android. Credenziale limitata ai soli avvisi (chiavi opache, priorità, tipo, stato review e tempi), separata da Viaggi e dall'agenda, revocabile con il dispositivo o disattivazione. Nessun titolo o descrizione nelle notifiche. Keystore separato senza autenticazione biometrica per consentire il background; nessuna credenziale di lettura agenda memorizzata in tale vault. WorkManager circa ogni 15 minuti, sveglie locali non esatte per i promemoria e ripetizioni, cache cifrata dei soli metadati valida fino a 24h dall'ultimo contatto e non oltre scadenza token. Avvisi urgenti/review immediati al rilevamento, scadenze 24h e termine, appuntamenti con orario anche 1h/15min. Data senza orario: promemoria 09:00 nel fuso server, non orario effettivo. Critici ripetuti 15/30/60min fino a presa visione locale per quella revisione; nuova modifica può riattivare. Presa visione non cambia stato task sul server. Canali Android e prova, limiti per non saturare il telefono. Nessuna garanzia di tempi esatti sotto Doze/risparmio energetico, app arrestata forzatamente o permessi negati. Nessun servizio push esterno introdotto; push immediato richiederà una scelta dedicata (es. FCM). Collaudo fisico Samsung obbligatorio, soprattutto schermata bloccata, revoca, modalità offline, riavvio e risparmio energetico.
