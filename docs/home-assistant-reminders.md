# Campanella NextDo per Home Assistant

La campanella è opzionale. Condivide un solo valore booleano: avviso presente/assente. Non invia titolo, descrizione, data o numero di impegni. Si attiva per attività urgenti, da verificare, scadute o previste entro 24 ore; esclude quelle completate o ancora rinviate.

In NextDo Web, Personale > Sicurezza e accesso > Campanella Home Assistant, genera una credenziale dedicata, revocabile. Copiala in secrets.yaml. L'indicatore richiede un URL HTTPS di NextDo raggiungibile da Home Assistant; un semplice URL ingress con autenticazione HA non è sufficiente.

```yaml
nextdo_indicator_url: "https://SOSTITUIRE-URL-NEXTDO/api/personal/ha-indicator"
nextdo_indicator_auth: "Bearer SOSTITUIRE-CREDENZIALE"
```

Integrare nella configurazione HA senza duplicare chiavi esistenti:

```yaml
binary_sensor:
  - platform: rest
    name: NextDo avviso personale
    unique_id: nextdo_private_indicator
    resource: !secret nextdo_indicator_url
    headers:
      Authorization: !secret nextdo_indicator_auth
    value_template: "{{ value_json.active }}"
    scan_interval: 30
```

Scheda manuale, visibile solo quando c'è un avviso:

```yaml
type: conditional
conditions:
  - condition: state
    entity: binary_sensor.nextdo_avviso_personale
    state: "on"
card:
  type: button
  entity: binary_sensor.nextdo_avviso_personale
  name: NextDo · Avviso personale
  icon: mdi:bell-ring
  show_state: false
  state_color: true
  icon_height: 42px
  tap_action:
    action: url
    url_path: "https://SOSTITUIRE-URL-NEXTDO/?nextdo=reminders"
```

Verificare l'entity_id effettivo e la configurazione prima del riavvio HA. Il link non contiene credenziali e NextDo richiede login e PIN. Una dashboard privata non impedisce necessariamente ad altri utenti HA di accedere allo stato dell'entità: evitare l'esposizione se anche la mera presenza di un avviso è riservata; valutare l'esclusione dal recorder. Se l'endpoint non è raggiungibile, lo stato non disponibile non equivale a nessun impegno. Nessuna modifica automatica alla dashboard reale.

Ricorrenze e rinvio Web/APK; notifiche offline e azioni rapide richiedono ancora collaudo.

## Avvisi locali Android

Il telefono conserva nel deposito cifrato di background esclusivamente gli identificativi opachi e gli orari delle notifiche già sincronizzate. Il lavoro locale non richiede rete, ma WorkManager non garantisce puntualità al minuto. Modifiche effettuate sul server durante un'interruzione si riflettono alla successiva sincronizzazione. Gli avvisi aprono l'area personale dopo lo sblocco: il completamento rapido nell'app e il rinvio richiedono una sessione valida e connessione. Nessuna modifica diretta non autenticata dalla notifica. Test fisico ancora richiesto. Versioni candidate Web 0.2.17-test / Android 0.2.12-test.
