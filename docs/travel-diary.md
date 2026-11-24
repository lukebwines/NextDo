# Diario di bordo — bozza integrata
- Registratore esplicitamente scelto dal web. API privata, batch idempotenti, cancellazione e revoca server.
- Android: foreground location service, notifica con sospensione, punti GPS cifrati con chiave separata dal vault; nuovi segmenti dopo interruzioni. Ripresa BOOT_COMPLETED solo con permessi, non garantita dopo force stop. Registrazione ogni almeno 30 s/20 m secondo il provider; batteria da misurare.
- Sincronizzazione su richiesta con sessione mobile sbloccata; punti non confermati conservati. Nessun token di background. Scollegare account elimina coda locale (sincronizzare prima). La revoca lato server non può spegnere un telefono offline.
- Web: selezione registratore e data (fuso browser), tracciato GPS vettoriale con zoom/pan, cronologia segmenti e distanza stimata; non usa cartografia esterna e non collega lacune.
- Ancora necessari: test reali su Samsung, sincronizzazione automatica in sessione, supporto mappa cartografica, soste, foto/note, esportazioni, backup e controllo quota/retention. Nessuna pubblicazione prima del collaudo.
