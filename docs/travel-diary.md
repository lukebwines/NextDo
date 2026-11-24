# Diario di bordo — fase 1
Bozza, non distribuire finché non sono stati collaudati Android e web.
- Un registratore esplicitamente selezionato per viaggio; altri dispositivi non possono inviare GPS.
- API con sessione mobile esistente, batch idempotenti, separazione per account/viaggio, cancellazione e disattivazione.
- Android: servizio in primo piano di tipo location con notifica e stop, avvio volontario, autorizzazioni esplicite; archiviazione locale cifrata con chiave dedicata utilizzabile a schermo spento; ripresa dopo riavvio quando consentita, nuova segmentazione dopo interruzioni; sincronizzare quando la sessione è sbloccata, senza salvare PIN o estendere i token esistenti. Rilevamento adattivo, misurare consumo reale.
- Web: scheda Diario di bordo, scelta registratore, calendario e mappa effettiva con segmenti distinti, timeline delle soste, GPX/PDF, foto/note, confronto itinerario; non inviare coordinate a terzi senza esplicita configurazione.
- Verificare backup/ripristino, separazione account, revoca, cancellazione, offline, risparmio energetico, arresto forzato, riavvio e firma release prima del viaggio.
