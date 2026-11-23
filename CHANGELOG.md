# Changes

## Version 1.1 (23 November 2026)

### New: Phone Serials tab
The Cisco IP Phone Serial Grabber is now a tab in Collab Ops Manager, after **MACD**, in English and Arabic.

* Reads the serial number, MAC, model, DN, firmware and hardware revision from each Cisco IP phone's own web pages.
* Targets can be IP addresses, ranges (`10.1.1.10-50`) or subnets (`10.1.1.0/24`), typed in or loaded from a .txt, .csv or .xlsx file.
* **Discover phones (RisPort)** asks the CUCM node you pick for its phones and their IPs, using the AXL login from the Cluster tab. Each phone's device name, DN and description are added to the results.
* Scans run in parallel and can be stopped. HTTPS (port 443) can be tried as well as HTTP, and a phone web login can be given if the pages ask for one.
* Results can be filtered, sorted and copied, and exported to Excel (with a summary by model) or CSV. Statuses are shown in Arabic on screen and stay English in the exported files.
* A scan keeps running when you switch language, and its results carry over.
* The settings are saved in `config.json` with the rest. The phone web password is never saved.
* Phones need *Web Access* enabled in CUCM (Phone › Product Specific Configuration).

### Fixed
* A line written to the activity log just before a language switch was missing from the on-screen log (it still reached the log file).

### Other
* New test `tests/test_serials_tab.py`. It also fails when any text on the tab has no Arabic translation.
* No new packages: `setup.bat` installs everything the tab needs.

## Version 1.0 (5 November 2026)

The first release, with these tabs: Cluster, SFTP Server, Backup (DRS), Upgrade / COP, MACD, Data Export and CLI Console. It works with CUCM / IM&P and Unity Connection, in English and Arabic.

Added and fixed on the way to 1.0:

* **27 October 2026:** first version, as the CUCM Maintenance Tool, with the built-in SFTP server, DRS backup, upgrades and COP installs, `file get` and the CLI console.
* **29 October 2026:** renamed to Collab Ops Manager. Added Unity Connection (health check, DRS backup with its own folder, trace collection and CUPI inventory export), the **Dry run (no changes)** check and the new icon.
* **3 November 2026:** added Arabic, and the MACD tab (formerly the separate UC Provisioner). The author and licence are now shown in the status bar.
* **4 November 2026:** CUCM node selection on the MACD tab and for the Excel inventory export. Added **Export phones + DNs to one file**.
* **5 November 2026:**
  * DRS device saves and backup starts that CUCM refused were reported as successful. They are now reported as failed.
  * A new backup no longer shows the previous backup's 100%.
  * The SFTP server no longer shares port 22 with another program on the PC.
  * Changing the SFTP user or password while the server was running made CUCM report a wrong username or password. The running server now uses the login on the SFTP Server tab.
