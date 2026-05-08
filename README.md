# Module Odoo 19 — Gestion de Rendez-Vous Médicaux Intelligents
## `clinic_appointment`

---

## 📋 Description

Module complet de gestion intelligente des rendez-vous pour **cliniques et hôpitaux publics**, développé sous Odoo 19.

---

## 👥 Acteurs et Rôles

| Acteur | Groupe Odoo | Fonctionnalités |
|--------|-------------|-----------------|
| **Administrateur** | `group_clinic_admin` | Gestion complète : utilisateurs, spécialités, médecins, patients, plannings, statistiques |
| **Secrétaire** | `group_clinic_secretary` | Organisation des plannings, gestion des RDV, dossiers patients |
| **Médecin** | `group_clinic_doctor` | Consultation de son planning, ses rendez-vous, son profil |
| **Patient** | `group_clinic_patient` | Prise de RDV, consultation de ses rendez-vous |

---

## 🗂️ Structure du Module

```
clinic_appointment/
│
├── __manifest__.py              # Manifeste Odoo 19
├── __init__.py
│
├── models/
│   ├── medical_speciality.py   # Spécialités médicales
│   ├── medical_doctor.py       # Médecins + calcul créneaux
│   ├── medical_patient.py      # Dossiers patients
│   ├── medical_appointment.py  # Rendez-vous (modèle principal)
│   └── medical_schedule.py     # Plannings hebdomadaires
│
├── views/
│   ├── medical_speciality_views.xml
│   ├── medical_doctor_views.xml
│   ├── medical_patient_views.xml
│   ├── medical_appointment_views.xml
│   ├── medical_schedule_views.xml
│   └── clinic_menus.xml
│
├── wizards/
│   ├── appointment_wizard.py          # Wizard prise RDV + annulation masse
│   └── appointment_wizard_views.xml
│
├── security/
│   ├── clinic_security.xml           # Groupes + Record Rules
│   └── ir.model.access.csv          # Droits CRUD par groupe
│
├── data/
│   ├── clinic_sequence.xml          # Séquences (RDV/, MED/, PAT/)
│   └── clinic_data.xml              # 10 spécialités par défaut
│
├── report/
│   ├── appointment_report.xml
│   └── appointment_report_template.xml
│
├── controllers/
│   └── main.py                      # API JSON (créneaux, stats)
│
└── static/src/
    ├── css/clinic_style.css
    └── js/clinic_dashboard.js
```

---

## 🔧 Installation

1. Copier le dossier `clinic_appointment/` dans votre répertoire `addons` Odoo
2. Relancer le serveur Odoo avec `--update=all` ou depuis l'interface
3. Aller dans **Apps** → Mettre à jour la liste → Rechercher "Clinique" → Installer

```bash
python odoo-bin -c odoo.conf -u clinic_appointment --stop-after-init
```

---

## 📦 Modèles de Données

### `medical.speciality` — Spécialités
- Nom, code unique, description
- Durée moyenne de consultation
- Compteurs : médecins, rendez-vous

### `medical.doctor` — Médecins
- Informations personnelles et professionnelles
- Lien vers compte utilisateur Odoo
- Planning hebdomadaire (One2many → `medical.schedule`)
- Méthode `get_available_slots(date)` pour calculer les créneaux libres

### `medical.patient` — Patients
- Dossier complet : CIN, date naissance, assurance (CNSS/CNRPS)
- Informations médicales : allergies, antécédents, médicaments
- Gouvernorats tunisiens intégrés

### `medical.appointment` — Rendez-Vous
**Workflow d'état :**
```
BROUILLON → CONFIRMÉ → EN ATTENTE → EN COURS → TERMINÉ
                                   ↘ ABSENT
              ↓ (annulé à tout moment sauf TERMINÉ)
           ANNULÉ
```

### `medical.schedule` — Plannings
- Par médecin, par jour de la semaine
- Vérification automatique des chevauchements
- Calcul du nombre max de RDV selon la durée de consultation

---

## 🔒 Sécurité

- **Record Rules** : chaque médecin voit uniquement ses RDV ; chaque patient voit uniquement les siens
- **Droits CRUD** granulaires par groupe
- **Séquences automatiques** : RDV/2025/04/0001, MED/0001, PAT/2025/00001

---

## 🌐 API JSON (Contrôleur)

| Route | Méthode | Description |
|-------|---------|-------------|
| `/clinic/available_slots` | POST | Créneaux disponibles d'un médecin à une date |
| `/clinic/doctors_by_speciality` | POST | Médecins d'une spécialité |
| `/clinic/dashboard_stats` | POST | Statistiques tableau de bord |
| `/clinic/check_slot` | POST | Vérifier disponibilité d'un créneau |

---

## 📊 Fonctionnalités Clés

- ✅ Wizard de prise de RDV guidé en 4 étapes
- ✅ Wizard d'annulation en masse
- ✅ Rapport PDF imprimable (fiche RDV)
- ✅ Vue calendrier hebdomadaire
- ✅ Vue graphique et pivot pour les statistiques
- ✅ Notifications par messagerie interne Odoo (chatter)
- ✅ 10 spécialités médicales pré-chargées
- ✅ Support CNSS / CNRPS / Assurance privée
- ✅ Gestion des urgences (priorité)
- ✅ Vérification automatique des conflits de planning

---

## 🎓 Projet de Fin d'Études

**Module développé dans le cadre d'un PFE** portant sur la digitalisation des services médicaux dans les établissements publics tunisiens.

---

*Compatible Odoo 19 Community & Enterprise*
