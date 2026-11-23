# Collab Ops Manager

One Windows app for CUCM / IM&P and Cisco Unity Connection (CUC) maintenance that comes with its own SFTP server, so you don't need a separate SFTP application.

**Version 1.1** (23 November 2026) adds the **Phone Serials** tab, which reads serial numbers, MACs and models from Cisco IP phones. See [CHANGELOG.md](CHANGELOG.md) for what changed in each version.

| Tab | What it does |
|---|---|
| **Cluster** | Connects to the publisher over SSH using the OS admin account, finds the nodes with `show network cluster`, shows each node's active and inactive version and installed COP files, and writes a pre/post-upgrade health report. |
| **SFTP Server** | The built-in SFTP server (paramiko). It is locked to one root folder, needs a password, and can be limited to cluster node IPs. It shows live transfers and has a button to add a Windows Firewall rule. |
| **Backup (DRS)** | Creates or updates the DRS network device that points at the built-in server, runs the backup, shows status and progress, and lists the backup files saved on this PC. Also shows history, device list and schedules, and can cancel a backup. |
| **Upgrade / COP** | Takes ISO/COP files placed in `<root>\upgrade` (with SHA-512/MD5 check), runs `utils system upgrade initiate` on the checked nodes one by one (publisher first) or all at once, shows upgrade status, and runs switch-version. |
| **MACD** | Move / Add / Change / Delete on CUCM over AXL, without the CUCM Administration pages (formerly the separate UC Provisioner / CUCM MACD Tool). It uses the AXL login from the Cluster tab and the **CUCM node** you pick at the top of the tab (the publisher by default; use the publisher for changes). **Search**: phones, lines/DNs, where a DN is used, users, with export to Excel. **Add**: phone or Jabber device with line and user. **Change / Move**: phone settings, MAC swap, line settings, move or share a DN. **Delete**: a phone or a DN after you type its name to confirm. **Bulk**: an Excel/CSV template, validate, then run. Every change is logged to `logs\audit_<month>.csv`, and the object is saved to `backups\` before it is changed or deleted. |
| **Phone Serials** | Reads the serial number, MAC, model, DN and firmware from Cisco IP phones' own web pages (formerly the separate Cisco IP Phone Serial Grabber). Enter IPs, ranges (`10.1.1.10-50`) or subnets (`10.1.1.0/24`), or load them from a .txt/.csv/.xlsx file. **Discover phones (RisPort)** asks the **CUCM node** you pick for its phones and their IPs, using the AXL login from the Cluster tab (that user needs RisPort access; on CUCM releases that refuse a wildcard search it also needs *Standard AXL API Access*). Results can be filtered, sorted, copied, and exported to Excel (with a summary by model) or CSV. Phones need *Web Access* enabled (CUCM › Phone › Product Specific Configuration). The phone web password is never saved. |
| **Data Export** | Runs `file get` (TFTP files, traces, syslog, CDR, DRS and install logs, or a custom spec) from the checked nodes into `<root>\export\<node>\...`. Exports the configuration inventory to Excel over AXL SQL (phones, lines, DNs, users, patterns, trunks, device pools, CSS, or custom SQL). Pick the node the inventory is read from in its **Node** box (the publisher by default). **Export phones + DNs to one file** writes a single Excel sheet with one row per phone line: phone details and DN details side by side. |
| **CLI Console** | A live SSH CLI session to any node, with quick-command buttons and masked password entry. |

## Unity Connection (CUC)
Enter the CUC publisher in the **Unity Connection cluster** box on the Cluster tab. **Connect & discover** then finds the nodes of both clusters, and each cluster uses its own OS admin account (leave the CUC one empty to use the CUCM account).
* **Backup:** pick *Unity Connection* on the Backup tab. It uses the `CUC` DRS feature and its own folder (`/backup_cuc`), so the two clusters' DRS rotation never deletes each other's backups. **Registered features** shows the names DRS accepts.
* **Upgrade / COP, file export, console:** CUC nodes appear in the node lists with type *Unity*.
* **Health check and dry run:** CUC nodes run `show cuc version`, `show cuc cluster status`, `show cuc dbserver disk` and `show cuc sysinfo`.
* **Inventory to Excel:** on the Data Export tab, pick *Unity Connection (CUPI REST)*. It exports users, call / directory / interview handlers, distribution lists, COS, templates, partitions, search spaces, routing rules, schedules, phone systems, port groups, ports and mailbox stores, plus any custom `/vmrest/...` path. It needs a CUC application administrator account and only reads (GET).

## Arabic
Pick **العربية** in the **Language / اللغة** box at the bottom of the window. The window redraws right to left (tabs, forms, tables and buttons mirrored) and keeps what you typed, the logs and a running SFTP server. The activity log and CLI output stay English: they carry CUCM's own messages. Translations are in `i18n.py` (English text is the key).

## Setup
1. Download version 1.1: on GitHub, open **Tags**, pick `v1.1` and download the ZIP, then unzip it to a folder of your own. If you update from an older copy, keep your `config.json`, `data`, `logs`, `backups` and `sftp_root` folders.
2. Run `setup.bat` once. It installs the packages and adds Start Menu and Desktop shortcuts.
3. On the SFTP Server tab, pick the IP address CUCM uses to reach this PC and click **Allow port in Windows Firewall**.
4. Start the SFTP server. On the Cluster tab, enter the publisher and the OS admin account, then click **Connect & discover nodes**.

Notes
* CUCM sees the SFTP root as `/`. Use `/backup` for DRS and `/upgrade` for ISO/COP files.
* Port 22 is the default. If Windows OpenSSH Server is running on this PC, it already uses 22, so stop it or use another port. Older DRS releases cannot use a different port.
* DRS keeps the SFTP password in its backup device. If you change the password, run **Create / update backup device** again.
* Passwords are saved only when you tick *Remember passwords*. They are encrypted with Windows DPAPI for the current user.
* `tests/test_e2e.py`, `tests/test_dryrun.py` and `tests/test_cuc.py` run the flows against `tests/fake_cucm.py`, a simulated CLI and CUPI. They use a temporary config, never yours. `tests/test_macd_tab.py` and `tests/test_serials_tab.py` check the MACD and Phone Serials tabs against simulated CUCM servers and phones, in both languages.
