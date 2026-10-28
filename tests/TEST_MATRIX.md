# GHL – Testmatrix

Stand: 28.10.2026. **86 Tests**, teilweise mit mehreren Unterfällen.

Die Matrix beschreibt den Umfang der Testsuite. Die Testnamen entsprechen der Ausgabe in GitHub Actions. Die Beschreibungen in der vollständigen Liste entsprechen den englischen Testbeschreibungen beziehungsweise Testnamen im Code.

## Abgedeckte Situationen

| Bereich | Beispiele | Erwartetes Verhalten |
|---|---|---|
| Normale Leseantworten | positive, negative und Nullwerte; Text; Umlaute | Wert unverändert auslesen, keine Wiederholung |
| Normale Schreibantworten | sofortiges ACK für Aktion oder sicheren Schreibzugriff | Erfolg, einmaliges Senden |
| Leere Werte | leere Beschreibung, leeres ACK-Wertfeld | Verhalten der jeweiligen Verarbeitungsebene erhalten |
| NACK | dokumentierte Fehlercodes sowie unbekannter Code | Ablehnung ohne blindes Wiederholen; -104 nur bei History als normales Ende |
| Beschädigte Antwort | fehlende Klammer, unbekannter Antworttext, fehlende Schreibbestätigung | kein erfundener Wert oder Erfolg; definierte Fehlerbehandlung |
| Kodierung | gültige Umlaute, ungültiges Byte in Text/Zahl/Bestätigung | Beschreibung mit Warnung ersetzen; andere Antworten nicht bereinigen |
| Verbindungsaufbau | sofortiger Erfolg, Wiederverwendung, schliessender Writer, Timeout, Socketfehler | vorhandene Regeln für Neuaufbau und begrenzte Wiederholung |
| Kommunikationsabbruch | Timeout, leere Byte-Antwort/EOF, Socketfehler | lesende Abfrage wiederholen; möglicherweise gesendete Aktion nicht wiederholen |
| Unklare sichere Schreibausführung | Timeout gefolgt von ACK oder NACK | ACK bestätigt; nach vorher unklarer Ausführung bleibt NACK-Ergebnis unklar |
| Parallelität und Abbruch | zwei angeforderte Befehle, abgebrochene Aktion | sequentielle Befehle; kein erneutes Senden, Sperre freigegeben |
| Schliessen | keine Verbindung, wiederholtes Schliessen, Fehler beim Warten | sicher schliessen und interne Referenzen freigeben |
| Eingaben | Beschreibungen an Längengrenze, Anführungs-/Steuerzeichen | gültige Werte zulassen, Protokollinjektion verhindern |
| Messwerte und Zustände | endliche Zahl, NaN/Inf/Text, 0/1 und anderer Zustand | ungültige Werte nicht als Messwert übernehmen; 0/1 nur wo dokumentiert |
| Kurven-Erkennung | zwei normale Punkte, null Punkte, mehr als 24, ungültige Zahl, NACK, fehlerhafter Punkt | bisherige Anzeige-/Warnregeln; höchstens Indizes 0–23 lesen |
| History-Datensätze | normaler Datensatz, falsche Feldzahl, ungültige Zahlen/Status, ungültiges Datum | gültige Daten übernehmen; einzelne ungültige Datensätze überspringen |
| History-Ablauf | Sortierung, Duplikate, Fortschritt, leere Liste, Verbindungsfehler | chronologische eindeutige Werte; Fortschritt weiterführen; Fehler korrekt melden |
| History-Ressourcen | SENSOR, KH ohne Index, ION mit Index | passende Befehlsform |
| Statistikberechnung | mehrere Werte einer abgeschlossenen Stunde; fehlende/future Werte | Mittelwert/Minimum/Maximum; keine Zukunftsstunde importieren |
| History-Import | gültige Werte, Sensorfehlerbits, NaN/Inf, fehlender Recorder/Entität | gültige Statistik übergeben; fehlerhafte Werte filtern; fehlende Voraussetzungen melden |
| Einrichtung und Geräteinfo | Fehler bei Geräteerkennung, Name vorhanden/leer | registrierte Bereinigung ausführen; Gerätekennung erhalten |
| Dateien | alle Produktions-Pythondateien und Übersetzungen | kompilierbar, gültiges JSON ohne doppelte Schlüssel |

## Bewusste Grenzen

- Simulierte Geräte und HA-Abhängigkeiten; kein vollständiger HA-Lauf oder echter Gerätetest.
- Die Recorder-Übergabe wird geprüft, nicht das tatsächliche Schreiben in eine HA-Datenbank.
- Keine Aussage über alle möglichen Paketaufteilungen eines TCP-Datenstroms. Die zuverlässige Antwortende-Erkennung ist weiterhin der zurückgestellte Aufgabenpunkt 1.
- Keine Tests der vollständigen Benutzeroberfläche oder aller einzelnen Entitätsklassen.
- Nicht jeder mögliche Zahlenwert oder jede einzelne Sensorart braucht einen eigenen Test; repräsentative Antworttypen, Grenz- und Fehlerfälle werden verwendet.
- Dies ist eine nachvollziehbare Abdeckung definierter Situationen, kein Beweis, dass alle denkbaren Gerätefehler erfasst sind.

## Vollständige Testliste

### Grundtests

| Nr. | Testname | Beschreibung |
|---|---|---|
| 1 | `APITests.test_read_retries_after_timeout` | read retries after timeout |
| 2 | `APITests.test_read_fails_after_two_attempts` | read fails after two attempts |
| 3 | `APITests.test_uncertain_action_is_not_repeated` | uncertain action is not repeated |
| 4 | `APITests.test_closed_connection_after_write_is_uncertain` | closed connection after write is uncertain |
| 5 | `APITests.test_explicitly_safe_write_can_retry` | explicitly safe write can retry |
| 6 | `APITests.test_nack_is_returned_without_retry` | nack is returned without retry |
| 7 | `APITests.test_malformed_write_reply_is_uncertain` | malformed write reply is uncertain |
| 8 | `APITests.test_nack_after_uncertain_safe_write_stays_uncertain` | nack after uncertain safe write stays uncertain |
| 9 | `APITests.test_invalid_description_character_is_replaced` | invalid description character is replaced |
| 10 | `APITests.test_valid_description_characters_survive` | valid description characters survive |
| 11 | `APITests.test_invalid_numeric_encoding_is_not_cleaned` | invalid numeric encoding is not cleaned |
| 12 | `APITests.test_invalid_write_encoding_never_repeats_action` | invalid write encoding never repeats action |
| 13 | `APITests.test_control_characters_never_reach_device` | control characters never reach device |
| 14 | `APITests.test_close_is_idempotent` | close is idempotent |
| 15 | `APITests.test_commands_do_not_overlap` | commands do not overlap |
| 16 | `ValueTests.test_pointcount_accepts_whole_counts` | pointcount accepts whole counts |
| 17 | `ValueTests.test_pointcount_rejects_invalid_counts` | pointcount rejects invalid counts |
| 18 | `ValueTests.test_description_validation` | description validation |
| 19 | `ValueTests.test_device_info_preserves_empty_name_and_identity` | device info preserves empty name and identity |
| 20 | `ValueTests.test_numeric_and_documented_switch_states` | numeric and documented switch states |
| 21 | `HistoryTests.test_bad_record_is_skipped_and_next_record_imported` | bad record is skipped and next record imported |
| 22 | `HistoryTests.test_empty_history_ends_normally` | empty history ends normally |
| 23 | `HistoryTests.test_other_nack_is_not_end_of_history` | other nack is not end of history |
| 24 | `HistoryTests.test_duplicate_timestamps_are_removed` | duplicate timestamps are removed |
| 25 | `HistoryTests.test_communication_error_propagates` | communication error propagates |
| 26 | `HistoryTests.test_unrepresentable_timestamp_is_rejected` | unrepresentable timestamp is rejected |
| 27 | `SetupTests.test_setup_registers_cleanup_before_connection_and_discovery` | setup registers cleanup before connection and discovery |
| 28 | `SourceChecks.test_all_production_python_files_compile` | all production python files compile |
| 29 | `SourceChecks.test_translations_are_valid_json_without_duplicate_keys` | translations are valid json without duplicate keys |

### Antworttypen und weitere Situationen

| Nr. | Testname | Beschreibung |
|---|---|---|
| 30 | `ResponseTypeTests.test_numeric_ack_on_first_attempt` | ACK with a numeric value succeeds on the first attempt. |
| 31 | `ResponseTypeTests.test_quoted_text_ack_on_first_attempt` | ACK with quoted text returns the text without surrounding quotes. |
| 32 | `ResponseTypeTests.test_empty_quoted_description` | An empty quoted description remains an empty string. |
| 33 | `ResponseTypeTests.test_ack_with_surrounding_whitespace` | Whitespace around a complete ACK is stripped. |
| 34 | `ResponseTypeTests.test_action_ack_on_first_attempt` | An action succeeds with a plain ACK and is sent once. |
| 35 | `ResponseTypeTests.test_safe_write_ack_on_first_attempt` | A safe value write succeeds with ACK without a retry. |
| 36 | `ResponseTypeTests.test_read_nacks_return_no_value` | Documented read errors and an unknown error code return no value. |
| 37 | `ResponseTypeTests.test_write_nacks_preserve_the_error_code` | Write rejections preserve the returned NACK for caller evaluation. |
| 38 | `ResponseTypeTests.test_unexpected_read_reply_is_an_api_error` | Unrecognised or whitespace-only read replies are reported as errors. |
| 39 | `ResponseTypeTests.test_ack_without_complete_value_returns_none` | ACK without a complete bracket pair returns no value. |
| 40 | `ResponseTypeTests.test_empty_unquoted_ack_value` | An empty ACK value remains empty at the transport layer. |
| 41 | `ResponseTypeTests.test_malformed_write_confirmations_are_uncertain` | An unexpected write reply never counts as successful confirmation. |
| 42 | `ResponseTypeTests.test_read_retries_after_eof` | A closed connection on a read is reconnected and retried. |
| 43 | `ResponseTypeTests.test_read_retries_after_socket_error` | A socket error on a read permits a retry. |
| 44 | `ResponseTypeTests.test_socket_error_after_action_does_not_retry` | A socket error after an action is sent leaves execution uncertain. |
| 45 | `ResponseTypeTests.test_connection_failure_before_sending_action_can_retry` | Failure before sending an action allows a connection retry. |
| 46 | `ResponseTypeTests.test_two_connection_failures_send_nothing` | Repeated connection failure is not a possibly executed action. |
| 47 | `ResponseTypeTests.test_repeated_bad_numeric_encoding_fails` | Repeated invalid encoding is reported instead of silently cleaned. |
| 48 | `ResponseTypeTests.test_damaged_description_envelope_is_not_repaired` | Only a complete quoted description envelope permits replacement. |
| 49 | `ResponseTypeTests.test_cancelled_action_is_not_repeated_and_unlocks` | Cancellation does not repeat an action or leave the command lock held. |
| 50 | `ResponseTypeTests.test_close_tolerates_socket_close_error` | Closing remains safe if waiting for socket closure raises OSError. |
| 51 | `ResponseTypeTests.test_close_without_connection` | Closing an unused client succeeds without connecting. |
| 52 | `ConnectionSetupTests.test_connect_success` | A new connection stores reader and writer returned by asyncio. |
| 53 | `ConnectionSetupTests.test_open_connection_is_reused` | An existing usable connection is not opened again. |
| 54 | `ConnectionSetupTests.test_closing_connection_is_replaced` | A connection whose writer is closing is replaced. |
| 55 | `ConnectionSetupTests.test_connect_errors_are_wrapped` | Socket failures and timeouts become GHL connection errors. |
| 56 | `ConnectionSetupTests.test_initial_check_succeeds_first_attempt` | Initial connection checking succeeds without another attempt. |
| 57 | `ConnectionSetupTests.test_initial_check_retries_until_success` | Initial setup retries a failed connection and then succeeds. |
| 58 | `ConnectionSetupTests.test_initial_check_stops_at_configured_limit` | Initial setup stops after its configured number of attempts. |
| 59 | `DiscoveryReplyTests.test_normal_two_point_curve` | A normal curve reads point count and two time/brightness pairs. |
| 60 | `DiscoveryReplyTests.test_zero_points_hidden_by_default` | A zero-point illumination channel stays hidden by default. |
| 61 | `DiscoveryReplyTests.test_zero_points_shown_when_requested` | Show-all includes a zero-point channel with an empty curve. |
| 62 | `DiscoveryReplyTests.test_oversized_count_is_limited_to_24` | An oversized count warns and reads only indices 0 through 23. |
| 63 | `DiscoveryReplyTests.test_fractional_and_nonfinite_counts_skip_channel` | Fractional, negative and non-finite counts skip the channel with a warning. |
| 64 | `DiscoveryReplyTests.test_nack_skips_unavailable_channel` | An unavailable illumination channel is skipped on NACK. |
| 65 | `DiscoveryReplyTests.test_unexpected_count_response_warns` | An unknown response to POINTCOUNT warns and skips the channel. |
| 66 | `DiscoveryReplyTests.test_missing_count_value_skips_channel` | ACK without a point count does not create a curve. |
| 67 | `DiscoveryReplyTests.test_count_communication_error_warns` | Communication failure for POINTCOUNT warns and skips the channel. |
| 68 | `DiscoveryReplyTests.test_malformed_point_does_not_hide_other_valid_points` | Discovery skips a malformed numeric point but reads the following point. |
| 69 | `HistoricalReplyTests.test_normal_historical_record` | A complete historical record returns timestamp, three values and status. |
| 70 | `HistoricalReplyTests.test_wrong_field_count_is_skipped` | DATARECORD with too few or too many fields is skipped. |
| 71 | `HistoricalReplyTests.test_bad_numeric_fields_are_skipped` | Invalid value or status fields do not prevent reading the next record. |
| 72 | `HistoricalReplyTests.test_missing_ack_envelope_stops_source` | A missing protocol envelope stops the source instead of inventing a record. |
| 73 | `HistoricalReplyTests.test_records_are_sorted_oldest_first` | Newest-first device records are returned in chronological order. |
| 74 | `HistoricalReplyTests.test_progress_advances_over_skipped_record` | Progress advances across a skipped record without repeating its index. |
| 75 | `HistoricalReplyTests.test_completed_hour_statistics` | Valid measurements produce hourly mean, minimum and maximum. |
| 76 | `HistoricalReplyTests.test_future_and_missing_values_do_not_make_statistics` | Future timestamps and missing values do not become completed-hour statistics. |
| 77 | `HistoricalReplyTests.test_singleton_resource_has_no_index` | KH Director history uses an unindexed resource command. |
| 78 | `HistoricalReplyTests.test_indexed_director_command` | ION Director history retains its resource index. |
| 79 | `HistoryImportResultTests.test_valid_data_is_submitted_to_recorder` | Valid historical data is submitted to the simulated Recorder. |
| 80 | `HistoryImportResultTests.test_sensor_error_masks_are_filtered` | Historical sensor-error and communication-error flags filter measurements. |
| 81 | `HistoryImportResultTests.test_nonfinite_history_values_are_filtered` | Historical NaN and infinite selected measurements are filtered. |
| 82 | `HistoryImportResultTests.test_recorder_missing_reports_failure` | Missing Recorder prevents reading and reports an unsuccessful import. |
| 83 | `HistoryImportResultTests.test_missing_entity_reports_failure` | An unregistered sensor prevents statistics submission. |
| 84 | `HistoryImportResultTests.test_empty_history_is_successful_without_statistics` | An empty history is successful and does not write statistics. |
| 85 | `HistoryImportResultTests.test_failed_history_read_reports_failure` | An unusable history response produces an unsuccessful import result. |
| 86 | `HistoryImportResultTests.test_history_connection_error_reports_failure` | A history connection error is converted to an unsuccessful import result. |

