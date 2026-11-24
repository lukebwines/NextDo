# Posta in uscita Cloudflare — 0.1.44-test

Configurare Email Sending e i destinatari verificati nell'account Cloudflare, con sottodominio dedicato. NextDo non modifica DNS, Worker o Email Routing. Usare un token ristretto all'account e al permesso Email Sending: Edit. Non condividere token in chat, issue o repository.

In NextDo Web → Impostazioni → Posta in uscita · Cloudflare, inserire Account ID, mittente, token e destinatari autorizzati. Salvare (ogni modifica disabilita gli invii reali e richiede nuovo test). Scegliere un indirizzo personale verificato, inviare una sola prova con evento sintetico, controllare posta e apertura del file, spuntare conferma e abilitare l'invio manuale.

Dalla scheda o esportazione multipla ICS scegliere Invia ICS via email, selezionare il destinatario e confermare. Titoli e date inclusi; descrizioni/luogo/link solo con scelta esplicita. Un destinatario per invio; solo amministratore; verifiche di visibilità anche sui singoli task. Il provider verifica gli indirizzi sul piano gratuito. Nessuna spedizione automatica o invito calendario.

Il registro distingue consegnato, accodato, rifiutato, mancata consegna, soppresso ed esito non certo. Non si ritentano invii automaticamente. Limite locale 30 richieste/ora e almeno 10 secondi tra invii. Se incerto, verificare Cloudflare prima di ripetere. Registro senza testi/titoli/indirizzi in chiaro, con hash destinatario e scadenza 90 giorni al successivo invio. Token cifrato nel file locale con permessi 0600; backup del Supervisor possono includere file e chiave: proteggerli. Backup ZIP interno non include configurazione locale. Non trasferire dati istituzionali senza autorizzazione.

API: https://developers.cloudflare.com/email-service/api/send-emails/rest-api/
