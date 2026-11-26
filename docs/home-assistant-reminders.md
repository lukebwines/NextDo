# NextDo — card Home Assistant

La card apre NextDo nell'area Attività e promemoria, dopo login e PIN. Nessun titolo, data, token o dato personale viene trasferito a Home Assistant. La visibilità di una dashboard non è un controllo di accesso.

Nella dashboard Home Assistant, aggiungere una scheda Manuale e incollare:

```yaml
type: vertical-stack
cards:
  - type: markdown
    content: |
      ## NextDo
      Attività e promemoria personali
  - type: button
    name: Apri promemoria
    icon: mdi:bell-check-outline
    color: teal
    icon_height: 48px
    tap_action:
      action: url
      url_path: "https://SOSTITUIRE-URL-NEXTDO/?nextdo=reminders"
```

Sostituire l'URL con l'indirizzo HTTPS effettivo di NextDo. Per installazioni disponibili esclusivamente tramite ingress, usare il percorso reale del pannello Home Assistant per aprire NextDo; il parametro di deep link potrebbe non essere inoltrato dal wrapper. Nessun token nei link. La card è statica, non mostra contatori reali.

## Prima fase promemoria

Ricorrenze delle attività con data, con ancora mensile/annuale e salto delle occorrenze passate; completare una ricorrenza programma quella successiva. Rinvio Web a 10/30/60/1440 minuti senza modificare la data dell'attività; notifiche online periodiche esistenti, non precise al minuto. APK: ricorrenze e consultazione del rinvio. Ancora da fare: rinvio APK, gestione/cancellazione rinvio, notifiche locali offline e azioni dalla notifica con autenticazione, test fisico, card dinamica opzionale con accesso per utente. Non esporre dati personali nelle entità HA condivise o nel recorder.
