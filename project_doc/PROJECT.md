# Projekt: Zeiterfassungsapplikation "ChronoLog"

## Code Vorgaben
* Variablennamen und Kommentare im Source Code immer auf Englisch
* Log-Meldungen und Konsolenoutput immer auf Englisch
* Im Root-Verzeichnis gibt es nur ein Python-Skript, das Main-Skript, welches zum Starten der Applikation verwendet wird. Alle weiteren Python-Skripte für Klassen oder Libraries sollen in entsprechend benannten Unterordnern abgelegt werden.

## Persona
Du agierst als Senior Fullstack Software-Entwickler mit mehreren Jahren Berufserfahrung. Du legst Wert auf klaren, sauberen und gut leserlichen Code. Es gibt keine Code-Duplikate, was mehrfach verwendet wird, wird in Methoden ausgelagert.

## Technologien
* Python3 als Programmiersprache
* Neueste Version (im Netz suchen) von HTMX
* Neueste Version (im Netz suchen) von Tailwind CSS für stilvolle UIs
* Neueste Version (im Netz suchen) von DuckDB für die Datenpersistenz

## Security
Sicherheit ist sehr wichtig und ernst zu nehmen. Beachte kleinlichst die [OWASP Top 10](https://owasp.org/Top10/2025/) für Entwickler.

## Logs
Log-Meldungen auf der Konsole sollen einen Logger verwenden und jeweils Datum (yyyy-mm-dd), Zeit (hh:mm:ss), Severity (DEBUG, INFO, WARNING, ERROR, ...) und natürlich die eigentliche Log-Meldung ausgeben. Wenn es das Terminal zulässt, sollen Datum und Zeit in dunkelorange dargestellt werden. Die Severity in einer Farbe entsprechend ihrer Dringlichkeit.

## Docker
Die Applikation soll schlussendlich als Docker-Container laufen. Daher soll auch immer ein Dockerfile geschrieben und ständig aktuell gehalten werden. Es soll auch eine Anleitung namens INSTALL-DOCKER.md erstellt werden, die beschreibt, wie man das Docker-Image mit dem Dockerfile baut und die Applikation als Docker-Container startet via Kommandozeile und auch via Docker-Compose-Datei-Beispiel.

## Diverses
* Immer ein requirements.txt führen und aktuell halten, wenn neue Libraries verwendet werden.
* Immer ein INSTALL.md führen mit einer Anleitung, wie man die Applikation installiert mit Python venv und die Requirements installiert und die Applikation startet.
* Beim Start der Applikation soll ein ASCII Art mit dem Namen der Applikation angezeigt werden. Wenn es das Terminal zulässt, dann gerne auch in Farbe, passend zum Projektnamen.

## Persistenzlayer
Für die Datenpersistenz soll wie bereits erwähnt die neueste Version von DuckDB zum Einsatz kommen. Die Applikation soll dabei befähigt sein, beim Start selbstständig Migrationen an DDL und DML vorzunehmen, falls diese notwendig sein sollten, falls z.B. eine neue Version der Applikation eine neue Spalte in einer Tabelle benötigt oder der Datentyp einer Spalte verändert wird und eine Migration der Daten dadurch benötigt wird. Es ist ganz extrem wichtig, dass dadurch **KEINE** Datenverluste in Kauf genommen werden oder auftreten können. Sollte beim Start der Applikation am angegebenen Dateipfad keine Datenbank gefunden werden, so soll eine Datenbank automatisch erstellt und initialisiert werden.

## Kurzbeschreibung
Applikationsname: **ChronoLog**  
Die Applikation ChronoLog soll es Benutzern ermöglichen, ihre täglichen Arbeiten in einem eleganten und intuitiven UI zu erfassen. Es geht dabei hauptsächlich um das Erfassen der Arbeitszeiten und damit der Berechnung der Über-/Minusstunden basierend auf den Vorgaben der SOLL-Arbeitszeiten. Man soll auch die Art der Tätigkeit in einem Textfeld erfassen können, dies dient aber eher der Information. Stunden sollen grundsätzlich, wenn nicht anders angegeben, immer in Dezimalform angezeigt werden, also z.B. 8.5 h für 8 Stunden und 30 Minuten.

## Applikationskonfiguration
Die Applikation soll eine Konfigurationsdatei namens "config.yaml" haben und sich im selben Verzeichnis wie das Python-Script befinden. Wie die Dateiendung schon verrät, soll die Datei im YAML-Format gespeichert werden. Über den Kommandozeilenparameter "-c" soll ein alternativer Pfad für die Datei angegeben werden können. Das ist auch der einzige Parameter, der von der Applikation akzeptiert wird.  
Die Datei soll folgende Parameter beinhalten:

* db\_file = Pfad zur DuckDB-Datenbank. Per Default soll die Datei einfach "chronolog.db" heissen.
* allow\_user\_registration = true/false Wert der bestimmt, ob sich Benutzer selber ein neues Konto anlegen können, oder ob das ein Administrator vornehmen muss. Default ist false.
* session\_timeout\_idle_min = Wert in Minuten, nach denen ein Benutzer automatisch ausgeloggt werden soll und die Session invalidiert wird, wenn der Benutzer keine Interaktionen mehr geführt hat mit der Applikation. Default ist 120
* session\_timeout\_hard_min = Wert in Minuten, nachdem der User in jedem Fall ausgeloggt wird und die Session invalidiert, auch wenn er noch kürzlich mit der Applikation interagiert hat. Default ist 600
* web\_port = Der Port, auf dem der Webserver laufen soll. Default ist 8080

## Benutzerkonten
Die Applikation soll zwei verschiedene Benutzertypen bekommen: "Benutzer" und "Administrator". Der Administrator hat dabei alle Funktionen des Benutzers, aber mit weitreichenderen Möglichkeiten zur Administration des Systems.

Ein Benutzer kann sich ein normales Benutzerkonto anlegen (wenn allow\_user\_registration auf true gesetzt ist) und kann dann mit der Zeiterfassung für sich selber beginnen.

Für das Anlegen eines Benutzerkontos muss ein Benutzername, Vorname, Nachname, E-Mail-Adresse und ein Passwort mit Wiederholung eingegeben werden. Das Passwort muss mindestens 6 Zeichen lang sein und im Minimum Zeichen und Zahlen beinhalten. Eine Überprüfung der Mail-Adresse ist nicht erforderlich.

Ein Administrator hat ein zusätzliches "Admin"-Menü, wo er diverse Einstellungen für globale Applikationsparameter vornehmen kann wie z.B. das Erfassen von "Chronos". Ausserdem hat er ein Menü für die Verwaltung von Benutzerkonten. Er kann alle Parameter eines Benutzerkontos bearbeiten und auch Passwörter zurücksetzen. Ausserdem soll er Benutzer "sperren" können. Der Benutzer erhält dann eine entsprechende Meldung auf der Login-Maske, wenn er versucht sich anzumelden.

## Erfassen von "Chronos"
Der Administrator hat die Möglichkeit in einem separaten Administrationsmenü sogenannte "Chronos" zu definieren. Ein Chronos ist dabei ein Set von Informationen und Regeln, die einem Benutzer zugeteilt werden. Ein Benutzer wird immer einem Chronos zugewiesen. Diese Zuweisung kann der Benutzer selbst in seinen eigenen Einstellungen vornehmen.

In einem Chronos kann man die folgenden Informationen definieren:

1. Die Soll-Arbeitszeit für einen normalen Arbeitstag. In der Regel sind das z.B. 8.0 oder 8.4 Stunden.
2. Eine Ausnahmeliste von speziellen Arbeits- oder Feiertagen. Ein Beispiel für einen solchen Tag ist z.B. der "25.12.", der 1. Weihnachtsfeiertag, er hat, wenn er auf einen Wochentag fällt, eine Soll-Arbeitszeit von 0.0 Stunden. Dann gibt es noch spezielle Tage wie z.B. das "Sechseläuten" in der Schweiz im Kanton Zürich. Dieser Tag hat eine Soll-Arbeitszeit von 4.2 Stunden. Diese speziellen Tage soll man in einer Tabelle eintragen können mit Tag und Monat, Soll-Arbeitszeit in Stunden und einer kleinen Beschreibung. Da die meisten Feiertage jährlich wiederkehrend sind, wird daher auf die Eingabe des Jahres verzichtet. Es soll aber dennoch ein Feld für das Jahr geben, welches optional ist. Dies soll Spezialfälle abdecken wie z.B. ein 50-jähriges Firmenjubiläum, welches nur in einem bestimmten Jahr stattfindet und z.B. mit einer Soll-Arbeitszeit von 0.0 angegeben wird, was bedeutet, dass die Mitarbeiter an diesem Tag frei haben.

## Startseite und Login
Wenn ein Benutzer noch nicht angemeldet ist, so soll er als erstes beim Aufrufen der Applikation die Login-Maske sehen. Die Login-Maske soll den Applikationsnamen "ChronoLog" anzeigen und eine Eingabemaske für Benutzername und Passwort und den "Anmelden"-Button. Wenn der allow\_user\_registration auf true gesetzt ist, soll es auch einen kleinen unscheinbaren Link geben, wo man sich ein neues Benutzerkonto anlegen kann.

Im Hintergrund der Login-Seite soll ein dezentes Bild zu sehen sein, das zum Thema der Applikation, also Zeiterfassung, passt. Dieses Bild soll im Rahmen der Entwicklung der Applikation ebenfalls noch erstellt werden.

Wenn der Benutzer ungültige Credentials eingibt, wird ihm einfach nur die Meldung "Ungültige Login Daten" angezeigt.

## Zeiterfassung
Nachdem sich der Benutzer erfolgreich eingeloggt hat, wird ihm das Herzstück der Applikation, die Zeiterfassungsmaske, angezeigt. Falls der Benutzer noch über eine gültige Session verfügt, wird er gleich von Anfang an auf diese Seite weitergeleitet, wenn er die Seite aufruft.

Oben auf der Seite soll der Nachname und Vorname des Benutzers angezeigt werden. Daneben der aktuelle Monat und das Jahr. Mit Links-/Rechts-Pfeiltasten kann man zwischen den Monaten wechseln. Mit der rechten Pfeiltaste kann man nur bis zum aktuellen Monat springen, nicht weiter. Mit der linken Pfeiltaste kann man beliebig durch die Monate/Jahre in die Vergangenheit springen bis zum Start-Monat/-Jahr, das in der Benutzerkonfiguration angegeben ist (nächstes Kapitel).

Zusätzlich wird im oberen Bereich angezeigt, wie viel die Soll-Stunden (Sollstunden / Tag) für einen normalen Arbeitstag betragen (laut der Chronos-Konfiguration) und wie viel die Soll-Arbeitsstunden für den aktuellen Monat (Sollstunden / Monat) betragen. Diese Monatsberechnung basiert auf der Chronos-Konfiguration von Soll-Stunden von normalen Arbeitstagen und eventuellen Spezialtagen wie dem Sechseläuten, wo nur 4.2 Stunden gearbeitet werden müssen.

Eine weitere sehr wichtige Information, die im oberen Bereich angezeigt werden soll, ist der aktuelle Stand des Zeitkontos und der übernommene Stand des Zeitkontos des letzten Monats. Befindet man sich bei der Ansicht im aktuellen Start-Monat/-Jahr, dann zeigt das Konto bei "Zeitkonto Vormonat" den Initialwert aus der Benutzerkonfiguration an (nächstes Kapitel). Das "Aktuelles Zeitkonto" berechnet sich dann immer aus  
**"Zeitkonto Vormonat" - "Sollstunden / Monat" + "Summe der bereits erfassten Arbeitsstunden pro Tag"**  
Im Idealfall ist man dann am Monatsende immer im positiven Bereich.

Ein Monat kann jederzeit über einen Button "Monat abschliessen" abgeschlossen werden. Dieses Flag soll auch so in der Datenbank existieren. Es hat aber nur Einfluss auf die Funktionalität des UIs. Ist ein Monat abgeschlossen, dann wird die gesamte Eingabetabelle Read-Only und zeigt einfach nur die eingegebenen Daten an. Man kann auch nur einen Monat weiterspringen mit den Pfeiltasten, wenn ein Monat abgeschlossen ist. Man kann einen aber auch ganz einfach wieder mit dem Button "Monat editieren" wieder öffnen, um Korrekturen vorzunehmen. Der Editieren-Button ist natürlich nur sichtbar, wenn der Monat als abgeschlossen markiert ist. Sowie der Abschliessen-Button nur sichtbar ist, solange der Monat noch geöffnet ist.

Die eigentliche Zeiterfassung passiert in einer Tabelle, bei der es für jeden Tag im Monat eine Zeile gibt. Ausgenommen sind Samstag/Sonntag und in den Chronos erfasste Tage, bei denen die Soll-Arbeitszeit 0.0 beträgt. Diese Tage werden per Default nicht angezeigt.

Die Tabelle hat folgende Spalten:

* Von (Zeitangabe hh:mm)
* Bis (Zeitangabe hh:mm)
* Total (aufsummierte Arbeitszeit in Stunden des aktuellen Eintrags und Tages)
* Beschreibung (Texteingabe von max. 256 Zeichen)
* Aktionen (Action-Buttons)

Auf jeder Zeile kann man eine Zeit "von" und "bis" eingeben. Die Zeit gibt man im Format "hh:mm" an. Die Eingabe soll aber flexibel sein. Man kann z.B. "08:00" oder "8:00" oder "800" eingeben können. Beim Verlassen des Eingabefelds wird dann der Wert, egal wie er eingegeben wurde, ins Format "hh:mm" abgeändert. Ganz rechts von jeder Zeile soll es einen "+" Button geben. Mit dem Button erzeugt man einen neuen Tabelleneintrag für denselben Tag. So kann man z.B. für den gleichen Tag einen Eintrag von 07:00 bis 12:00 und von 13:00 bis 17:00 machen. Die nächste Spalte ist das aufsummierte Total der Arbeitszeit für den aktuellen Tag. Für unser vorheriges Beispiel würde der erste Eintrag ein Total von 5.0h anzeigen. Der zweite Eintrag dann 9.0h, da der zweite Eintrag ja zum selben Tag gehört und damit insgesamt 9 Stunden an diesem Tag gearbeitet wurde. Innerhalb eines Tages soll auch immer geprüft werden, dass man keine überlappenden Zeiten eingeben kann. Also auf einer Zeile 7:00 bis 12:00 und auf der nächsten Zeile 11:30 bis 13:00 muss zu einem Fehler führen und dem Benutzer angezeigt werden.

In der Beschreibung kann der Benutzer einen Text eingeben, was er während der Zeit gemacht hat. Muss es aber nicht, das Feld ist optional.

In der "Aktionen"-Spalte wurde bereits der "+" Button erwähnt, er gehört in diese Spalte. Zusätzlich soll es noch die folgenden beiden Aktions-Buttons geben:

1. Pfeil nach oben: Dieser Aktions-Button soll im ersten Eintrag des aktuellen Tages auftauchen, wenn der Tag von dieser Zeile nach einem Sonntag oder einem Tag mit Soll-Arbeitszeit 0.0 aus der Chronos-Konfiguration kommt. Klickt man darauf, dann wird oberhalb dieser Zeile ein neuer Eintrag erstellt für den eigentlichen Sonntag oder den freien Tag. So kann man dennoch eine Arbeitszeit erfassen, auch wenn es eigentlich ein freier Tag wäre.
2. Pfeil nach unten: Dieser Aktions-Button soll im letzten Eintrag des aktuellen Tages auftauchen, wenn der Tag von dieser Zeile vor einem Samstag oder einem Tag mit Soll-Arbeitszeit 0.0 aus der Chronos-Konfiguration kommt. Klickt man darauf, dann wird unterhalb dieser Zeile ein neuer Eintrag erstellt für den eigentlichen Samstag oder den freien Tag. So kann man dennoch eine Arbeitszeit erfassen, auch wenn es eigentlich ein freier Tag wäre.

Als letzten Aktions-Button erhält jede Zeile noch ein "X", mit dem man den aktuellen Eintrag löschen kann. Ausgenommen sind Zeilen, die angezeigt werden müssen. Also immer mindestens eine Zeile für jeden Tag des Monats, der kein Samstag/Sonntag ist und auch kein freier Tag mit Soll-Arbeitszeit 0.0 laut Chronos-Konfiguration.

Mit einem "Speichern"-Button werden die eingegebenen Daten in der Datenbank gespeichert.

## Absenzerfassung
Neben der Zeiterfassung und der Seite für die Benutzerkonfiguration soll es für den Benutzer noch eine Seite für die Absenzerfassung geben.

Hier können in einer Tabelle Absenzen erfasst werden mittels einem "Hinzufügen"-Button. Die Tabelle hat folgende Spalten:

* Datum von
* Datum bis
* Zeit (h)
* Beschreibung (Texteingabe von max. 256 Zeichen)
* Aktionen (Action-Buttons)

In "Datum von" und "Datum bis" kann ein Datum des aktuellen Monats eingegeben werden. Sind "Datum von" und "Datum bis" an demselben Tag, kann auch eine "Zeit (h)" in Stunden angegeben werden. Dies ermöglicht es, dass man z.B. einen Arzttermin von 2.5 Stunden eintragen kann. Aber Achtung: Die eingegebene Zeit aus der Zeiterfassung plus die hier manuell eingegebene Zeit darf die maximale Soll-Arbeitszeit eines Tages aus der Chronos-Konfiguration nicht überschreiten, sonst gibt es eine Fehlermeldung. Überspannt der Zeitrahmen von "Datum von" und "Datum bis" mehrere Tage, dann wird dort automatisch die Soll-Arbeitszeit eines Tages laut der Chronos-Konfiguration eingetragen werden. Auch hier soll es einen Fehler geben, wenn im definierten Zeitraum dennoch ein Eintrag in der Zeiterfassung vorhanden ist. Im Beschreibungsfeld kann ein Freitext eingegeben werden und im Aktionen-Feld gibt es einfach einen "X"-Button zum Löschen des aktuellen Eintrags. Mit einem "Speichern"-Button werden die eingegebenen Daten in der Datenbank gespeichert.

## Benutzerkonfiguration
Ein Benutzer hat auch die Möglichkeit über eine "Einstellungen"-Seite, einige Parameter für sich selber zu konfigurieren.

1. Monat und Jahr, ab wann mit der Erfassung der Daten in ChronoLog gestartet wird.
2. Der Initialwert des Zeitkontos, mit dem im Start-Monat/-Jahr begonnen wird.
3. Dropdown zur Auswahl der Chronos-Konfiguration
4. Benutzername. Dieser kann angepasst werden. Benutzer werden innerhalb des Systems über eine eindeutige ID identifiziert, welche automatisch beim Erfassen des Benutzers vergeben wird.
5. Vorname / Nachname
6. Passwort ändern

## Vorgehen
Lies dieses Dokument aufmerksam durch. Mach Dir ein Bild der Anforderungen und stelle einen Plan der verschiedenen UIs und der Architektur des Systems zusammen. Wenn das getan ist, sprich Unklarheiten, die Dir auf dem Weg aufgefallen sind, an und frag nach. Passe dieses Dokument an, wenn wichtige Fragen oder Unklarheiten geklärt wurden und es Sinn macht, die neuen Erkenntnisse in den entsprechenden Kapiteln zu erweitern. Wenn dann alles klar ist, arbeite autonom an der Erstellung der Applikation. Viel Erfolg!

## Geklärte Annahmen (Implementierung)

Die folgenden Punkte wurden bei der Umsetzung festgelegt:

### Erster Administrator
Solange noch kein Benutzer in der Datenbank existiert, ist die Registrierung **immer** freigeschaltet – unabhängig von `allow_user_registration`. Der **erste** registrierte Benutzer wird automatisch Administrator. Danach gilt `allow_user_registration` wie konfiguriert. Administratoren können weitere Benutzer unter Admin → Benutzer anlegen.

### Absenzen und Zeitkonto
Absenzen fliessen in die **Summe der erfassten Stunden** und damit ins Zeitkonto ein:
- Eintägige Absenz mit Angabe «Zeit (h)»: dieser Stundenwert zählt.
- Eintägige Absenz ohne Stundenangabe: Soll-Arbeitszeit des Tages (Chronos).
- Mehrtägige Absenz: pro Tag im Zeitraum die jeweilige Soll-Arbeitszeit laut Chronos.

### Web-Framework
Server-seitig: **Flask** mit Jinja2-Templates, HTMX und Tailwind CSS (CDN). Sessions serverseitig in DuckDB; Cookie enthält nur die Session-ID (HttpOnly, SameSite=Lax). CSRF-Schutz auf allen zustandsändernden Requests.

### UI-Sprache
Benutzeroberfläche und Fehlermeldungen: **Deutsch**. Code, Kommentare und Logs: **Englisch**.

### Technologien (Stand Implementierung)
- Python: 3.11+ (Docker-Image: 3.14)
- DuckDB Python: 2.0.0
- HTMX: 2.0.11
- Tailwind CSS: Play CDN (v4-Linie)
- Flask: 3.1.3
- Werkzeug: 3.1.9
- bcrypt: 5.0.0

### Monat-Navigation
Zum nächsten Monat (Pfeil rechts) darf nur gewechselt werden, wenn der aktuelle Monat abgeschlossen ist und der Zielmonat nicht in der Zukunft liegt. In die Vergangenheit bis zum konfigurierten Startmonat des Benutzers.
