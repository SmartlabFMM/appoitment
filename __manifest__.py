# -*- coding: utf-8 -*-
{
    'name': 'MedRdv',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Module de gestion des rendez-vous pour cliniques et hôpitaux publics',
    'description': """
        Module complet de gestion de rendez-vous médicaux pour cliniques et hôpitaux publics.
        
        Fonctionnalités :
        - Gestion des spécialités médicales
        - Gestion des médecins et leurs plannings
        - Prise de rendez-vous par les patients
        - Organisation des plannings par la secrétaire
        - Tableau de bord pour chaque acteur
        - Notifications automatiques
        - Rapports et statistiques
    """,
    'author': 'Arafet Tekaya',
    'website': '',
    'license': 'LGPL-3',
    'external_dependencies': {'python': ['bcrypt', 'jwt']},
    'depends': [
        'base',
        'mail',
        'calendar',
        'web',
        'portal',
    ],
    'data': [
        # Security
        'security/clinic_security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/clinic_sequence.xml',
        'data/clinic_data.xml',

        # Views - Speciality
        'views/medical_speciality_views.xml',

        # Views - Doctor
        'views/medical_doctor_views.xml',

        # Views - Patient
        'views/medical_patient_views.xml',

        # Views - Appointment
        'views/medical_appointment_views.xml',

        # Views - Schedule
        'views/medical_schedule_views.xml',

        # Views - Menus
        'views/clinic_menus.xml',

        # Wizards
        'wizards/appointment_wizard_views.xml',

        # Report
        'report/appointment_report.xml',
        'report/appointment_report_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'clinic_appointment/static/src/css/clinic_style.css',
            'clinic_appointment/static/src/js/clinic_dashboard.js',
        ],
    },
    'images': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
