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

### New: Phone Backgrounds tab
Wallpapers for Cisco phones, after **Phone Serials**, in English and Arabic.

* Resizes your pictures for each phone model and makes the full-size picture, the thumbnail and the `List.xml` in that model's TFTP folder:
  * 79XX: 7941/7942/7961/7962 (greyscale), 7945/7965, 7970/7971, 7975
  * 88XX: 8841, 8845, 8851, 8861, 8865 (`Desktops/800x480x24`)
  * PhoneOS: Desk Phone 9851, 9861, 9871 and the NR models (`Desktops/DP-98xx`), and the 8875 (`Desktops/1024x600x24`)
* The PhoneOS phones get their own List.xml format: `wallpaper-`/`thumbnail-` files, a light or dark theme per picture, and a version number.
* Optional company logo for the PhoneOS phones (`logo.png`, listed as `Name="logo"`), scaled in proportion with its transparency kept.
* Pictures that don't match the screen shape either fill the screen (edges cut) or show whole with black bars. A preview shows the result per model.
* Short file names: **Rename**, or **Rename all…** to number them from one name (Wall1, Wall2, …).
* **Save to folder…** or **Save as ZIP…** keeps the files in the TFTP folder layout, for a manual upload.
* **Upload to TFTP servers** uploads to the ticked CUCM nodes through OS Administration (the same as *TFTP File Management*), using the OS admin login from the Cluster tab.
  * It keeps what each `List.xml` on the server already lists, such as Cisco's default PhoneOS wallpapers, adds the new pictures at the end, and sets the version above the server's. Untick the option to replace the list.
  * It then restarts **Cisco Tftp** through CUCM's Serviceability API with the AXL user from the Cluster tab (the CLI cannot restart feature services), and checks that the node hands out the new `List.xml`.
* Phones show the pictures only when CUCM allows it: Common Phone Profile › *Enable End User Access to Phone Background Image Setting*.

### Fixed
* SFTP server: a client that logs in with another program's user name, such as a CUCM pushing CDR files to a billing server on the same PC, is explained once in the activity log; its retries are no longer logged every few minutes. The same goes for connections refused by the allowed IP list.
* Dry-run report: a password echoed back in two pieces could appear in the CLI transcript. The whole transcript is now masked again before it is written.

### Other
* New tests: `tests/test_serials_tab.py`, `tests/test_backgrounds_tab.py` and `tests/test_sftp_foreign_login.py`. The tab tests also fail when any text has no Arabic translation.
* New package: Pillow, for the pictures. Run `setup.bat` again after updating. Without it, only the Phone Backgrounds tab stops working.

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
