# NextDo — specifica notifiche email istituzionali

Stato: SPECIFICA, NON ATTIVO. Nessun invio abilitato finché non sia stata autorizzata una identità applicativa dall'amministrazione Microsoft 365 dell'Ateneo. Nessuna credenziale o dato CdS in GitHub.

## Canale di invio

- Provider: Exchange Online / Microsoft 365 (Univr).
- Host SMTP verificato: smtp.office365.com; porta 587; STARTTLS; OAuth 2.0 (XOAUTH2).
- Mittente, tenant ID, client ID, autorizzazioni della casella e consenso amministratore: DA CONFIGURARE solo localmente, previa autorizzazione.
- Mai password GIA o token nel repository, nei log, in eccezioni o in backup non cifrati.
- OAuth: scegliere modalità delegated o application secondo autorizzazioni dell'IT di Ateneo; implementare rinnovo token e controllo scadenza. Il semplice possesso di una casella non garantisce il permesso di invio automatico.
- Mail disabilitata finché il test di invio autorizzato non ha esito positivo; disabilitata per dati reali finché non sono verificati sicurezza, backup e policy istituzionali.

## Configurazione UI

Impostazioni > Notifiche email: stato disabilitato / configurato / testato; mittente autorizzato; indicatore di connessione Microsoft 365; test invio ad indirizzo confermato; orario invio; template in italiano; scelta dei promemoria; registro degli esiti (senza contenuti riservati).

## Parametri local-only

La configurazione non segreta puo essere conservata in /data (provider, mittente, preferenze, timezone). Segreti OAuth e refresh token devono risiedere in file locali con permessi restrittivi; nessuna esportazione in chiaro. Per i backup cifrare o escludere i token.

## Modello dati

- user_email_preferences(user_id, enabled, verified_email, consented_at)
- task_reminder_rules(task_id, days_before, overdue_cadence, enabled)
- notification_outbox(id, task_id, recipient_user_id, event_key, scheduled_at, status, attempts, last_error_code, sent_at)
- provider_settings(id, sender, enabled, tested_at)
- event_key univoca per task, destinatario, tipologia, occorrenza e scadenza; deduplica tramite indice UNIQUE.
- Ogni destinatario deve avere accesso alla task e scelta esplicita delle notifiche. La pubblicazione sul Display non autorizza invio di email.

## Motore automatico

1. Scheduler periodico lato backend, fuso Europe/Rome per presentazione e UTC per le scadenze archiviate.
2. Calcolo eventi 7,3,1,0 giorni prima (valori configurabili) e avviso scaduto solo se aperto.
3. Controllo visibilita, appartenenza ai gruppi e stato globale/per CdS al momento dell'invio.
4. Accodamento idempotente; invio TLS+OAuth2; gestione risposta provider; retry con backoff solo per errori temporanei.
5. Tracciare esito e correlation id, senza titolo task o indirizzo completo nei log tecnici.
6. Arrestare promemoria al completamento o alla revoca della condivisione.
7. Applicare limite invii e protezione contro loop/duplicati.

## Contenuto dell'email

Oggetto breve: NextDo - Promemoria scadenza.
Body minimalista con titolo, data, priorita e link HTTPS verso l'attivita dopo autenticazione. No descrizioni, note, elenchi CdS o allegati per impostazione predefinita. Il link non deve includere token in URL.

## Sicurezza e verifica

- Nessuna mail con dati istituzionali finché non sia stata autorizzata l'installazione su infrastruttura privata e chiarita la base organizzativa di utilizzo.
- Test: mancato consenso OAuth, revoca autorizzazioni, token scaduto, crash/ripresa worker, duplicati, utente non autorizzato, gruppi modificati, attività completata, multi-CdS.
- Feature flag NEXTDO_EMAIL_ENABLED=false come predefinito.
- Accesso locale separato da Ingress/Cloudflare; non abilitare tunnel finché non si completano audit e test di sicurezza.

## Fonti

- Documentazione ufficiale Univr (MFA, configurazione caselle condivise): https://www.univr.it/it/i-nostri-servizi/autenticazione-a-fattori-multipli-mfa-multi-factor-authentication/come-utilizzare-mfa-su-windows/come-configurare-le-caselle-condivise-per-accedere-con-mfa-windows
- Microsoft OAuth SMTP: https://learn.microsoft.com/en-us/exchange/client-developer/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth/
