# Diario di bordo — importazione Google
Sostituisce il prototipo GPS archiviato, senza permessi di posizione, servizi in background o modifiche alla firma APK.
- Android: aprire un viaggio, Diario, scegliere JSON esportato, sbloccare nuovamente se il selettore di file ha chiuso la sessione, riaprire Diario, scegliere le date, analizzare e confermare.
- Il file originale non è inviato. Sono ammessi solo coordinate, orari, modalità e distanze nel periodo scelto; date riferite agli offset originali. Gli eventi che attraversano i limiti sono esclusi, i percorsi filtrati per punto. Limiti: 32 MB file, 30.000 elementi, 5 MB import, 367 giorni inclusivi.
- Un nuovo import confermato sostituisce la cronologia di quel viaggio; duplicati identici eliminati. Nessuna modifica alle prenotazioni.
- Il server controlla la sessione, il proprietario, i campi e le date. Dati in database privato; non inclusi nello ZIP del viaggio. La cancellazione è esplicita dal web.
- Web: schema vettoriale privato, filtro giornaliero, statistiche Google e collegamento a foto/note esistenti. Cartografia reale non ancora integrata.
- Formati Google variabili: supporto iniziale semanticSegments o array di segmenti, non convalidato su esportazione reale del Samsung. Test automatici e collaudo prima di rilascio.
