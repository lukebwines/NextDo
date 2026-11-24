# NextDo Android — roadmap prioritaria

## Obiettivo
Un'unica app NextDo, con dashboard generale e due aree separate, come sul web. Viaggi rimane un modulo personale; nessuna perdita di dati o funzioni esistenti. L'identificativo uk.archis.nextdoviaggi, la firma APK, i tag android-v e gli asset nextdo-viaggi.apk/json restano invariati per compatibilità.

| Versione Android indicativa | Obiettivo | Stato |
| --- | --- | --- |
| 0.1.7-test | Nuovo nome e icona; dashboard, Professionale, Personale, Impostazioni, navigazione modulare; Viaggi integro | Implementazione, test richiesti |
| 0.1.8-test | Associazione professionale esplicita, API dedicate e minimali, agenda settimanale, scadenze e appuntamenti anche da verificare, arretrati, priorità | Da sviluppare |
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
