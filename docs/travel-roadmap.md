# NextDo Viaggi — roadmap aggiornata

## Principi
- Motore universale, senza dati personali nel repository; il Raspberry resta fonte autorevole, separato dall'area professionale.
- Stesso formato ZIP, migrazioni additive, revisioni, test e collaudo prima dei rilasci.
- GroqCloud per testo, Geoapify per geografia; fotografie caricate manualmente.
- Firma Android permanente, aggiornamenti da GitHub Releases con conferma di sistema. Nessuna chiave privata nel repository.

## Versioni e stato
- Pubblicato: NextDo 0.1.35-test / Android 0.1.4-test: area Viaggi, prenotazioni e percorsi, dashboard Oggi, navigazione, PDF, copia offline cifrata, PIN/biometria, accesso ricordato, firma stabile e aggiornamenti.
- Integrazione in collaudo: NextDo 0.1.36-test / Android 0.1.5-test (PR 45, incorpora PR 44). Import ZIP, creazione viaggi e modifica online di titolo/sottotitolo, giornate, eventi e dati principali prenotazioni. Nessuna sovrascrittura automatica; PDF e campi avanzati preservati. Diario di bordo: import JSON Cronologia Google Maps filtrato sul telefono, anteprima e conferma, storico privato sul server, schema tracciati e statistiche sul web. Non registra GPS in background.
- Prima della pubblicazione: test congiunti, APK firmato, verifica import reale Samsung e aggiornamento sul dispositivo. Il formato Google non è ancora verificato su esportazione reale; storico fuori dallo ZIP, backup/restore dedicato da verificare.

## Scaletta dei prossimi interventi

| Fase | Obiettivo | Funzioni |
| --- | --- | --- |
| 1 | Completare gestione mobile e diario | Collaudo ZIP, creazione/modifica e cronologia; gestione date viaggio, eliminazioni controllate, campi avanzati e più luoghi, allegati; diario e storico su Android; backup storico |
| 2 | Acquisizione automatica | Inbox viaggi@posta.archis.uk dedicata da configurare, separata dal lavoro, allegati privati, analisi GroqCloud, associazione viaggio, deduplicazione, conferma e tracciabilità; condivisione Android PDF/email |
| 3 | Sincronizzazione e offline | Aggiornamento automatico delle copie, indicatori stato/revisione, note e checklist modificabili, modifiche offline accodate con gestione conflitti; copie di più viaggi da valutare |
| 4 | Modalità viaggio | Promemoria privati, check-in, cancellazioni, riconsegne, fusi orari, test modalità aereo e cambio fuso; notifiche senza dati sensibili |
| 5 | Mappe e contesto | Mappa interattiva del piano e della cronologia effettiva, confronto previsto/effettivo, ottimizzazione percorsi, POI, meteo con fonte e data |
| 6 | Assistente e guide | Q&A sul viaggio, suggerimenti da confermare, guide con fonti e date verificabili |
| 7 | Condivisione | Account indipendenti, inviti selettivi, permessi e revoca |
| 8 | Gestione avanzata | Budget multivaluta (già parziale), spese/ricevute da Android, ripartizione, modelli, ICS, diario fotografico e riepilogo PDF |
| 9 | Versione 1.0 | Sicurezza, backup/ripristino comprensivo del diario, accessibilità, prestazioni, compatibilità, manuale e collaudo remoto/online/offline |

Ordine e numerazioni successive indicativi, non impegni di consegna. La priorità concordata è completare le tre funzioni Android e integrare il diario; poi inbox email e acquisizione documenti, senza duplicare archivi.

## Vincoli Android
- URL HTTPS diretto o gateway/VPN; l'ingress Home Assistant non è un endpoint mobile autonomo. Nessuna esposizione di API professionali, database o credenziali.
- Pairing specifico Viaggi, PIN iniziale, biometria/credenziale Android, Keystore, token a scadenza e revocabili; revoca online non cancella copie offline esistenti.
- Chiavi GroqCloud/Geoapify restano sul server. Cronologia: il JSON originale e i periodi esclusi non vengono trasmessi.
- Cifre e firma APK conservate separatamente; nessuna reinstallazione necessaria se firma e identificativo restano uguali e versionCode aumenta.
