// Moteur de traduction FR/EN de l'interface Web PiDecoder.
//
// Volontairement sans dépendance externe (pas de librairie i18n), pour
// rester cohérent avec la philosophie « dépendances minimales » du projet.
// Chargé avant app.js : expose window.I18N = {t, lang, setLang,
// applyTranslations}. La langue choisie est stockée dans un cookie
// `pidecoder_lang` (non HttpOnly) afin d'être lisible à la fois par ce
// script et par config-web.py (voir scripts/i18n.py côté serveur), pour que
// les messages renvoyés par l'API soient dans la même langue que l'interface.
(function(global){
  'use strict';

  const COOKIE_NAME='pidecoder_lang';
  const DEFAULT_LANG='fr';

  const STRINGS={
    fr:{
      'login.username':'Utilisateur',
      'login.password':'Mot de passe',
      'login.submit':'Connexion',

      'header.engine_unknown':'État inconnu',
      'header.version':'Administration v{version}',
      'shortcuts.title':'Raccourcis clavier',
      'common.save':'Sauvegarder',
      'common.apply':'Appliquer',
      'common.logout':'Déconnexion',
      'common.username':'Utilisateur',
      'common.password':'Mot de passe',
      'common.none':'Aucun',
      'common.none_f':'Aucune',

      'nav.cams':'📹 Caméras',
      'nav.onvif':'🌐 ONVIF',
      'nav.layout':'🖥 Disposition',
      'nav.system':'💻 Système',
      'nav.security':'🔐 Sécurité',
      'nav.backup':'💾 Sauvegarde',

      'cams.title':'Caméras',
      'cams.hint':'Déplacement uniquement avec la poignée ☰. Les champs texte restent sélectionnables normalement.',
      'cams.add':'+ Ajouter',
      'cams.delete':'Supprimer',
      'cams.active':'active',
      'cams.audio_enabled':'Audio',
      'cams.audio_enabled_hint':'À cocher si le flux RTSP de cette caméra diffuse aussi une piste audio (interphone, sonnette...). Active le bouton son en vue plein écran ; décoché par défaut car ça change aussi certains réglages réseau de la mosaïque pour cette caméra.',
      'cams.name':'Nom',
      'cams.ip_address':'Adresse IP',
      'cams.rtsp_port':'Port RTSP',
      'cams.rtsp_path':'Chemin RTSP',
      'cams.grid_resolution':'Résolution mosaïque',
      'cams.grid_fps':'FPS mosaïque',
      'cams.default_values':'Valeurs PiDecoder',
      'cams.focus_resolution':'Résolution plein écran',
      'cams.focus_fps':'FPS plein écran',
      'cams.advanced_summary':'URL avancées / mode manuel',
      'cams.grid_url_label':'URL mosaïque',
      'cams.focus_url_label':'URL plein écran',
      'cams.manual_url_hint':'Adresse vide = les URL manuelles sont conservées.',
      'cams.default_name':'Caméra',
      'cams.new_camera_prefix':'Caméra',

      'layout.title':'Disposition de la mosaïque',
      'layout.hint':'Déplace et redimensionne les caméras actives dans la grille. Les collisions sont refusées et la disposition est sauvegardée automatiquement.',
      'layout.reset_order':'Réinitialiser l’ordre',
      'layout.columns':'Colonnes',
      'layout.rows':'Lignes',
      'layout.fullscreen_on_start':'Plein écran au démarrage',
      'layout.focus_audio_default_on':'Micro actif par défaut en plein écran',
      'layout.template.uniform.title':'Grille uniforme',
      'layout.template.uniform.subtitle':'Toutes les caméras en 1×1',
      'layout.template.main.title':'Caméra principale',
      'layout.template.main.subtitle':'Une grande caméra, les autres autour',
      'layout.template.dual.title':'Deux principales',
      'layout.template.dual.subtitle':'Deux grandes vues puis les autres',
      'layout.template.free.title':'Libre',
      'layout.template.free.subtitle':'Conserver la disposition actuelle',

      'sys.title':'Système',
      'sys.hint':'État du Raspberry Pi, de PiDecoder et informations utiles au support.',
      'sys.refresh':'Actualiser',
      'sys.copy_report':'Copier le rapport',
      'sys.health':'Santé',
      'sys.services':'Services',
      'sys.recent_logs':'Journaux récents',
      'sys.logs_hint':'Journaux de PiDecoder et de l’administration Web.',
      'sys.log_lines_label':'Lignes',
      'sys.open_tab_hint':'Ouvre l’onglet Système pour charger les diagnostics.',
      'sys.unavailable':'Indisponible',
      'sys.value_not_recognized':'Valeur non reconnue',
      'sys.throttling_active':'Actif',
      'sys.throttling_past':'Historique',
      'sys.throttling_none':'Aucun',
      'sys.vcgencmd_unavailable':'vcgencmd indisponible',
      'sys.card.temperature':'Température CPU',
      'sys.card.cores':'{count} cœur(s)',
      'sys.card.memory_units':'{used} / {total} Mo',
      'sys.uptime.dhm':'{days} j {hours} h {minutes} min',
      'sys.uptime.hm':'{hours} h {minutes} min',
      'sys.uptime.m':'{minutes} min',

      'sec.title':'Mot de passe administrateur',
      'sec.hint':'Le mot de passe actuel est requis. Le nouveau mot de passe doit être saisi deux fois à l’identique.',
      'sec.current_password':'Mot de passe actuel',
      'sec.new_password':'Nouveau mot de passe',
      'sec.confirm_password':'Confirmer le nouveau mot de passe',
      'sec.change_button':'Modifier le mot de passe',

      'sec.tls_title':'Certificat HTTPS',
      'sec.tls_hint':'Génère ou importe le certificat de l\'interface Web, et active ou désactive HTTPS.',
      'sec.tls_toggle_warning':'Ceci redémarre l\'interface Web et recharge la page dans quelques secondes.',
      'sec.tls_status_active':'HTTPS actif',
      'sec.tls_status_inactive':'HTTPS inactif (HTTP simple)',
      'sec.tls_subject':'Sujet',
      'sec.tls_expires':'Expire le',
      'sec.tls_san':'Noms couverts (SAN)',
      'sec.tls_disabled_present':'Un certificat désactivé est conservé et sera réutilisé à la réactivation.',
      'sec.tls_enable_button':'Activer HTTPS',
      'sec.tls_disable_button':'Désactiver HTTPS',
      'sec.tls_restarting':'Redémarrage du service, redirection dans quelques secondes…',
      'sec.tls_generate_button':'Générer un nouveau certificat auto-signé',
      'sec.tls_generated_active':'Nouveau certificat généré et actif immédiatement.',
      'sec.tls_generated_staged':'Nouveau certificat généré — il sera utilisé à l\'activation de HTTPS.',
      'sec.tls_import_title':'Importer un certificat',
      'sec.tls_import_requires_https':'L\'import n\'est possible qu\'en HTTPS — active d\'abord HTTPS ci-dessus.',
      'sec.tls_import_cert_label':'Certificat (.pem)',
      'sec.tls_import_key_label':'Clé privée (.pem)',
      'sec.tls_import_button':'Importer',
      'sec.tls_import_missing_file':'Sélectionne le certificat et la clé à importer',
      'sec.tls_imported_active':'Certificat importé et actif immédiatement.',

      'backup.title':'Sauvegarde et restauration',
      'backup.export_title':'Exporter',
      'backup.export_hint':'Télécharge les caméras et la disposition dans un fichier JSON portable. Le mot de passe Web n\'est pas exporté.',
      'backup.export_button':'📤 Exporter la configuration',
      'backup.import_title':'Importer',
      'backup.import_hint':'L\'import crée une sauvegarde des fichiers actuels avant de les remplacer.',
      'backup.import_button':'📥 Importer la configuration',

      'onvif.title':'ONVIF — Gestion des caméras',
      'onvif.hint':'Recherche locale ou identification manuelle par adresse IPv4. Choix séparé des profils mosaïque et plein écran.',
      'onvif.discover_button':'🔎 Rechercher les caméras',
      'onvif.username':'Utilisateur ONVIF',
      'onvif.password':'Mot de passe ONVIF',
      'onvif.manual_title':'Ajouter manuellement par IPv4',
      'onvif.manual_hint':'Pour une caméra non découverte, située sur un autre réseau routé ou dont WS-Discovery est désactivé.',
      'onvif.manual_address':'Adresse',
      'onvif.manual_port':'Port ONVIF',
      'onvif.manual_path':'Chemin ONVIF',
      'onvif.identify_button':'Identifier',
      'onvif.reidentify_button':'Réidentifier',
      'onvif.discovering':'Recherche ONVIF en cours…',
      'onvif.devices_found':'{count} équipement(s) ONVIF trouvé(s).',
      'onvif.invalid_ipv4':'Adresse IPv4 invalide',
      'onvif.invalid_port':'Port ONVIF invalide',
      'onvif.manual_camera_name':'Caméra {ip}',
      'onvif.card_not_found':'Carte ONVIF introuvable',
      'onvif.identifying':'Identification…',
      'onvif.codec_unknown':'Codec ?',
      'onvif.resolution_unknown':'résolution ?',
      'onvif.fps_unknown':'fps ?',
      'onvif.profile_fallback':'Profil',
      'onvif.identify_first':'Identifie d’abord la caméra',
      'onvif.saving':'Enregistrement…',
      'onvif.camera_saved_fallback':'Caméra enregistrée',
      'onvif.update_button':'Mettre à jour',
      'onvif.add_button':'Ajouter à PiDecoder',
      'onvif.connecting':'Connexion ONVIF en cours…',
      'onvif.identified_toast':'✔ Caméra identifiée',
      'onvif.log_to_send':'Log à transmettre :',
      'onvif.no_device_found':'Aucun équipement découvert. Consulte les diagnostics ci-dessus.',
      'onvif.device_fallback':'Équipement ONVIF',
      'onvif.ip_unknown':'IP inconnue',
      'onvif.identified_badge':'Identifiée',
      'onvif.already_configured':'Déjà configurée',
      'onvif.new_badge':'Nouvelle',
      'onvif.manufacturer':'Fabricant',
      'onvif.model':'Modèle',
      'onvif.serial_number':'Numéro de série',
      'onvif.name_in_pidecoder':'Nom dans PiDecoder',
      'onvif.grid_profile':'Profil mosaïque',
      'onvif.focus_profile':'Profil plein écran',
      'onvif.usable_profiles_count':'{count} profil(s) H264/RTSP utilisable(s)',
      'onvif.no_usable_profile':'Aucun profil RTSP utilisable',
      'onvif.all_profiles_summary':'Tous les profils détectés',
      'onvif.token_label':'Token : ',
      'onvif.hardware_announced':'Matériel annoncé : ',
      'onvif.location_label':'Emplacement : ',
      'onvif.discovered_addresses':'Adresses ONVIF découvertes',

      'ptz.command_title':'Commande PTZ',
      'ptz.pad_aria':'Commandes directionnelles PTZ',
      'ptz.up':'Monter',
      'ptz.left':'Gauche',
      'ptz.stop':'Arrêter',
      'ptz.right':'Droite',
      'ptz.down':'Descendre',
      'ptz.zoom_in':'Zoom +',
      'ptz.zoom_out':'Zoom −',
      'ptz.preset_label':'Preset',
      'ptz.goto_preset':'Aller au preset',
      'ptz.no_preset':'Aucun preset ONVIF détecté pour ce profil.',
      'ptz.hold_hint':'Maintiens une commande pour déplacer la caméra. Le relâchement envoie immédiatement Stop.',
      'ptz.no_preset_selected':'Aucun preset sélectionné',
      'ptz.moving':'Déplacement…',
      'ptz.preset_called':'✔ Preset PTZ appelé',

      'diag.discovery_title':'Diagnostics de découverte',
      'diag.interfaces':'Interfaces :',
      'diag.probes_sent':'Probes envoyés :',
      'diag.packets_received':'Paquets reçus :',
      'diag.xml_packets':'Paquets XML :',
      'diag.message_types':'Types de messages :',
      'diag.probe_matches':'ProbeMatch trouvés :',
      'diag.xml_errors':'Erreurs XML :',
      'diag.socket_errors':'Erreurs socket',
      'diag.unknown_xml_samples':'Extraits XML inconnus',
      'diag.sample_from':'{type} depuis {ip}',
      'diag.detailed_log':'Journal détaillé',
      'diag.fd_open':'FD ouverts',
      'diag.hardware_decode':'Décodage matériel',
      'diag.release_candidate':'Version candidate',
      'diag.release_stable':'Stable',
      'diag.configured':'Configurées',
      'diag.active':'Actives',
      'diag.disabled':'Désactivées',
      'diag.onvif_cameras':'Caméras ONVIF',
      'diag.rtsp_streams':'Flux RTSP',
      'diag.web_admin':'Administration Web',
      'diag.no_logs':'Aucun journal disponible.',
      'diag.state_stable':'Stable',
      'diag.state_error':'Erreur',
      'diag.state_warning':'Attention',
      'diag.loading':'Chargement…',
      'diag.refreshed_toast':'✔ Diagnostics actualisés',
      'diag.report_copied':'✔ Rapport copié',

      'shortcuts.switch_tab':'Changer d’onglet',
      'shortcuts.close_panels':'Fermer les fenêtres',
      'notifications.title':'Historique des notifications',
      'notifications.recent':'Notifications récentes',
      'notifications.clear':'Effacer',
      'notifications.none':'Aucune notification récente',

      'api.unavailable':'Fonction indisponible sur cette version du serveur',
      'api.invalid_response':'Réponse serveur invalide ({status})',
      'api.server_error_fallback':'Erreur serveur',
      'login.error_fallback':'Mot de passe incorrect',
      'session.expired':'Session expirée',

      'mosaic.too_small_for_placement':'La grille est trop petite pour cette disposition.',
      'mosaic.not_enough_space_resize':'Pas assez de place pour agrandir cette caméra',
      'mosaic.unknown_address':'Adresse inconnue',
      'mosaic.drag_hint':'Glisser pour déplacer',
      'mosaic.no_active_camera':'Aucune caméra active',
      'mosaic.too_small_for_template':'La grille est trop petite pour ce modèle',
      'mosaic.saving':'Sauvegarde…',
      'mosaic.saved':'✔ Disposition sauvegardée — clique sur Appliquer',

      'save.done':'✓ Sauvegarde effectuée',

      'password.current_required':'Le mot de passe actuel est obligatoire.',
      'password.twice_required':'Le nouveau mot de passe doit être saisi deux fois.',
      'password.min_length':'Le nouveau mot de passe doit contenir au moins 8 caractères.',
      'password.mismatch_client':'Les mots de passe ne correspondent pas.',
      'password.match_ok':'✔ Les mots de passe correspondent.',
      'password.changing':'Modification…',
      'password.changed_toast':'✔ Mot de passe modifié',

      'engine.running':'PiDecoder en cours',
      'engine.stopped':'PiDecoder arrêté',

      'export.failed':'Export impossible',
      'export.done':'✓ Configuration exportée',
      'import.select_file':'Sélectionne un fichier JSON',
      'import.done_toast':'✓ Configuration importée',
    },
    en:{
      'login.username':'Username',
      'login.password':'Password',
      'login.submit':'Sign in',

      'header.engine_unknown':'Unknown status',
      'header.version':'Administration v{version}',
      'shortcuts.title':'Keyboard shortcuts',
      'common.save':'Save',
      'common.apply':'Apply',
      'common.logout':'Log out',
      'common.username':'Username',
      'common.password':'Password',
      'common.none':'None',
      'common.none_f':'None',

      'nav.cams':'📹 Cameras',
      'nav.onvif':'🌐 ONVIF',
      'nav.layout':'🖥 Layout',
      'nav.system':'💻 System',
      'nav.security':'🔐 Security',
      'nav.backup':'💾 Backup',

      'cams.title':'Cameras',
      'cams.hint':'Only drag using the ☰ handle. Text fields remain normally selectable.',
      'cams.add':'+ Add',
      'cams.delete':'Delete',
      'cams.active':'active',
      'cams.audio_enabled':'Audio',
      'cams.audio_enabled_hint':'Check this if this camera\'s RTSP stream also carries an audio track (intercom, doorbell...). Enables the sound button in the fullscreen view; off by default since it also changes some mosaic network settings for this camera.',
      'cams.name':'Name',
      'cams.ip_address':'IP address',
      'cams.rtsp_port':'RTSP port',
      'cams.rtsp_path':'RTSP path',
      'cams.grid_resolution':'Mosaic resolution',
      'cams.grid_fps':'Mosaic FPS',
      'cams.default_values':'PiDecoder defaults',
      'cams.focus_resolution':'Fullscreen resolution',
      'cams.focus_fps':'Fullscreen FPS',
      'cams.advanced_summary':'Advanced URLs / manual mode',
      'cams.grid_url_label':'Mosaic URL',
      'cams.focus_url_label':'Fullscreen URL',
      'cams.manual_url_hint':'Empty address = the manual URLs are kept.',
      'cams.default_name':'Camera',
      'cams.new_camera_prefix':'Camera',

      'layout.title':'Mosaic layout',
      'layout.hint':'Move and resize active cameras in the grid. Collisions are rejected and the layout is saved automatically.',
      'layout.reset_order':'Reset order',
      'layout.columns':'Columns',
      'layout.rows':'Rows',
      'layout.fullscreen_on_start':'Fullscreen on startup',
      'layout.focus_audio_default_on':'Microphone on by default in fullscreen',
      'layout.template.uniform.title':'Uniform grid',
      'layout.template.uniform.subtitle':'All cameras at 1×1',
      'layout.template.main.title':'Main camera',
      'layout.template.main.subtitle':'One large camera, the others around it',
      'layout.template.dual.title':'Two main cameras',
      'layout.template.dual.subtitle':'Two large views, then the others',
      'layout.template.free.title':'Free',
      'layout.template.free.subtitle':'Keep the current layout',

      'sys.title':'System',
      'sys.hint':'Status of the Raspberry Pi and PiDecoder, plus information useful for support.',
      'sys.refresh':'Refresh',
      'sys.copy_report':'Copy report',
      'sys.health':'Health',
      'sys.services':'Services',
      'sys.recent_logs':'Recent logs',
      'sys.logs_hint':'PiDecoder and Web administration logs.',
      'sys.log_lines_label':'Lines',
      'sys.open_tab_hint':'Open the System tab to load diagnostics.',
      'sys.unavailable':'Unavailable',
      'sys.value_not_recognized':'Unrecognized value',
      'sys.throttling_active':'Active',
      'sys.throttling_past':'Past',
      'sys.throttling_none':'None',
      'sys.vcgencmd_unavailable':'vcgencmd unavailable',
      'sys.card.temperature':'CPU temperature',
      'sys.card.cores':'{count} core(s)',
      'sys.card.memory_units':'{used} / {total} MB',
      'sys.uptime.dhm':'{days}d {hours}h {minutes}m',
      'sys.uptime.hm':'{hours}h {minutes}m',
      'sys.uptime.m':'{minutes}m',

      'sec.title':'Administrator password',
      'sec.hint':'The current password is required. The new password must be entered twice, identically.',
      'sec.current_password':'Current password',
      'sec.new_password':'New password',
      'sec.confirm_password':'Confirm new password',
      'sec.change_button':'Change password',

      'sec.tls_title':'HTTPS certificate',
      'sec.tls_hint':'Generate or import the Web interface\'s certificate, and turn HTTPS on or off.',
      'sec.tls_toggle_warning':'This restarts the Web interface and reloads the page in a few seconds.',
      'sec.tls_status_active':'HTTPS active',
      'sec.tls_status_inactive':'HTTPS inactive (plain HTTP)',
      'sec.tls_subject':'Subject',
      'sec.tls_expires':'Expires on',
      'sec.tls_san':'Covered names (SAN)',
      'sec.tls_disabled_present':'A disabled certificate is kept and will be reused when re-enabled.',
      'sec.tls_enable_button':'Enable HTTPS',
      'sec.tls_disable_button':'Disable HTTPS',
      'sec.tls_restarting':'Restarting the service, redirecting in a few seconds…',
      'sec.tls_generate_button':'Generate a new self-signed certificate',
      'sec.tls_generated_active':'New certificate generated and active immediately.',
      'sec.tls_generated_staged':'New certificate generated — it will be used once HTTPS is enabled.',
      'sec.tls_import_title':'Import a certificate',
      'sec.tls_import_requires_https':'Import is only available over HTTPS — enable HTTPS above first.',
      'sec.tls_import_cert_label':'Certificate (.pem)',
      'sec.tls_import_key_label':'Private key (.pem)',
      'sec.tls_import_button':'Import',
      'sec.tls_import_missing_file':'Select the certificate and key to import',
      'sec.tls_imported_active':'Certificate imported and active immediately.',

      'backup.title':'Backup and restore',
      'backup.export_title':'Export',
      'backup.export_hint':'Downloads the cameras and layout as a portable JSON file. The Web password is not exported.',
      'backup.export_button':'📤 Export configuration',
      'backup.import_title':'Import',
      'backup.import_hint':'Importing creates a backup of the current files before replacing them.',
      'backup.import_button':'📥 Import configuration',

      'onvif.title':'ONVIF — Camera management',
      'onvif.hint':'Local discovery or manual identification by IPv4 address. Choose the mosaic and fullscreen profiles separately.',
      'onvif.discover_button':'🔎 Search for cameras',
      'onvif.username':'ONVIF username',
      'onvif.password':'ONVIF password',
      'onvif.manual_title':'Add manually by IPv4',
      'onvif.manual_hint':'For a camera that wasn\'t discovered, on another routed network, or with WS-Discovery disabled.',
      'onvif.manual_address':'Address',
      'onvif.manual_port':'ONVIF port',
      'onvif.manual_path':'ONVIF path',
      'onvif.identify_button':'Identify',
      'onvif.reidentify_button':'Re-identify',
      'onvif.discovering':'ONVIF search in progress…',
      'onvif.devices_found':'{count} ONVIF device(s) found.',
      'onvif.invalid_ipv4':'Invalid IPv4 address',
      'onvif.invalid_port':'Invalid ONVIF port',
      'onvif.manual_camera_name':'Camera {ip}',
      'onvif.card_not_found':'ONVIF card not found',
      'onvif.identifying':'Identifying…',
      'onvif.codec_unknown':'Codec ?',
      'onvif.resolution_unknown':'resolution ?',
      'onvif.fps_unknown':'fps ?',
      'onvif.profile_fallback':'Profile',
      'onvif.identify_first':'Identify the camera first',
      'onvif.saving':'Saving…',
      'onvif.camera_saved_fallback':'Camera saved',
      'onvif.update_button':'Update',
      'onvif.add_button':'Add to PiDecoder',
      'onvif.connecting':'Connecting to ONVIF…',
      'onvif.identified_toast':'✔ Camera identified',
      'onvif.log_to_send':'Log to send:',
      'onvif.no_device_found':'No device discovered. Check the diagnostics above.',
      'onvif.device_fallback':'ONVIF device',
      'onvif.ip_unknown':'Unknown IP',
      'onvif.identified_badge':'Identified',
      'onvif.already_configured':'Already configured',
      'onvif.new_badge':'New',
      'onvif.manufacturer':'Manufacturer',
      'onvif.model':'Model',
      'onvif.serial_number':'Serial number',
      'onvif.name_in_pidecoder':'Name in PiDecoder',
      'onvif.grid_profile':'Mosaic profile',
      'onvif.focus_profile':'Fullscreen profile',
      'onvif.usable_profiles_count':'{count} usable H264/RTSP profile(s)',
      'onvif.no_usable_profile':'No usable RTSP profile',
      'onvif.all_profiles_summary':'All detected profiles',
      'onvif.token_label':'Token: ',
      'onvif.hardware_announced':'Announced hardware: ',
      'onvif.location_label':'Location: ',
      'onvif.discovered_addresses':'Discovered ONVIF addresses',

      'ptz.command_title':'PTZ control',
      'ptz.pad_aria':'PTZ directional controls',
      'ptz.up':'Up',
      'ptz.left':'Left',
      'ptz.stop':'Stop',
      'ptz.right':'Right',
      'ptz.down':'Down',
      'ptz.zoom_in':'Zoom +',
      'ptz.zoom_out':'Zoom −',
      'ptz.preset_label':'Preset',
      'ptz.goto_preset':'Go to preset',
      'ptz.no_preset':'No ONVIF preset detected for this profile.',
      'ptz.hold_hint':'Hold a control to move the camera. Releasing it immediately sends Stop.',
      'ptz.no_preset_selected':'No preset selected',
      'ptz.moving':'Moving…',
      'ptz.preset_called':'✔ PTZ preset called',

      'diag.discovery_title':'Discovery diagnostics',
      'diag.interfaces':'Interfaces:',
      'diag.probes_sent':'Probes sent:',
      'diag.packets_received':'Packets received:',
      'diag.xml_packets':'XML packets:',
      'diag.message_types':'Message types:',
      'diag.probe_matches':'ProbeMatch found:',
      'diag.xml_errors':'XML errors:',
      'diag.socket_errors':'Socket errors',
      'diag.unknown_xml_samples':'Unknown XML samples',
      'diag.sample_from':'{type} from {ip}',
      'diag.detailed_log':'Detailed log',
      'diag.fd_open':'Open FDs',
      'diag.hardware_decode':'Hardware decoding',
      'diag.release_candidate':'Release Candidate',
      'diag.release_stable':'Stable',
      'diag.configured':'Configured',
      'diag.active':'Active',
      'diag.disabled':'Disabled',
      'diag.onvif_cameras':'ONVIF cameras',
      'diag.rtsp_streams':'RTSP streams',
      'diag.web_admin':'Web administration',
      'diag.no_logs':'No logs available.',
      'diag.state_stable':'Stable',
      'diag.state_error':'Error',
      'diag.state_warning':'Warning',
      'diag.loading':'Loading…',
      'diag.refreshed_toast':'✔ Diagnostics refreshed',
      'diag.report_copied':'✔ Report copied',

      'shortcuts.switch_tab':'Switch tab',
      'shortcuts.close_panels':'Close panels',
      'notifications.title':'Notification history',
      'notifications.recent':'Recent notifications',
      'notifications.clear':'Clear',
      'notifications.none':'No recent notifications',

      'api.unavailable':'Feature unavailable on this server version',
      'api.invalid_response':'Invalid server response ({status})',
      'api.server_error_fallback':'Server error',
      'login.error_fallback':'Incorrect password',
      'session.expired':'Session expired',

      'mosaic.too_small_for_placement':'The grid is too small for this layout.',
      'mosaic.not_enough_space_resize':'Not enough room to enlarge this camera',
      'mosaic.unknown_address':'Unknown address',
      'mosaic.drag_hint':'Drag to move',
      'mosaic.no_active_camera':'No active camera',
      'mosaic.too_small_for_template':'The grid is too small for this template',
      'mosaic.saving':'Saving…',
      'mosaic.saved':'✔ Layout saved — click Apply',

      'save.done':'✓ Saved',

      'password.current_required':'The current password is required.',
      'password.twice_required':'The new password must be entered twice.',
      'password.min_length':'The new password must be at least 8 characters long.',
      'password.mismatch_client':'Passwords do not match.',
      'password.match_ok':'✔ Passwords match.',
      'password.changing':'Changing…',
      'password.changed_toast':'✔ Password changed',

      'engine.running':'PiDecoder running',
      'engine.stopped':'PiDecoder stopped',

      'export.failed':'Export failed',
      'export.done':'✓ Configuration exported',
      'import.select_file':'Select a JSON file',
      'import.done_toast':'✓ Configuration imported',
    },
  };

  function readCookie(name){
    const pattern=new RegExp('(?:^|; )'+name.replace(/([.$?*|{}()[\]\\/+^])/g,'\\$1')+'=([^;]*)');
    const match=document.cookie.match(pattern);
    return match?decodeURIComponent(match[1]):null;
  }

  function writeCookie(name,value){
    document.cookie=name+'='+encodeURIComponent(value)+'; Path=/; Max-Age=31536000; SameSite=Lax';
  }

  let currentLang=readCookie(COOKIE_NAME)==='en' ? 'en' : DEFAULT_LANG;

  function lang(){
    return currentLang;
  }

  function t(key,vars){
    const table=STRINGS[currentLang]||STRINGS[DEFAULT_LANG];
    let value=Object.prototype.hasOwnProperty.call(table,key)
      ? table[key]
      : (STRINGS[DEFAULT_LANG][key]!==undefined ? STRINGS[DEFAULT_LANG][key] : key);

    if(vars){
      Object.keys(vars).forEach(name=>{
        value=value.split('{'+name+'}').join(String(vars[name]));
      });
    }

    return value;
  }

  function applyTranslations(root){
    const scope=root||document;

    scope.querySelectorAll('[data-i18n]').forEach(el=>{
      el.textContent=t(el.getAttribute('data-i18n'));
    });

    scope.querySelectorAll('[data-i18n-placeholder]').forEach(el=>{
      el.setAttribute('placeholder',t(el.getAttribute('data-i18n-placeholder')));
    });

    scope.querySelectorAll('[data-i18n-title]').forEach(el=>{
      el.setAttribute('title',t(el.getAttribute('data-i18n-title')));
    });

    scope.querySelectorAll('[data-i18n-aria-label]').forEach(el=>{
      el.setAttribute('aria-label',t(el.getAttribute('data-i18n-aria-label')));
    });

    scope.querySelectorAll('.lang-option').forEach(el=>{
      el.classList.toggle('active',el.getAttribute('data-lang')===currentLang);
    });

    document.documentElement.lang=currentLang;
  }

  function setLang(next){
    if(next!=='fr' && next!=='en'){
      return;
    }

    currentLang=next;
    writeCookie(COOKIE_NAME,next);
    applyTranslations();

    if(typeof global.onLanguageChange==='function'){
      global.onLanguageChange(next);
    }

    fetch('/api/language',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({lang:next}),
    }).catch(()=>{});
  }

  global.I18N={t,lang,setLang,applyTranslations};
})(window);
