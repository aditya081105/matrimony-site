User Model: CustomUser (fields: full_name, is_paid, caste_community)
Profile Model: Profile (fields: bio, father_name, profile_photo)
App Names: users, search, payments
URLs: profiles/ -> profile_list
Project: Django Marriage Bureau
User Model: users.CustomUser (Inherits AbstractUser). Fields: full_name, is_paid, caste_community, occupation, height_feet.
Profile Model: users.Profile (Linked to CustomUser). Fields: bio, father_name, mother_name, city_hometown, profile_photo.
Key Logic: is_paid (Boolean) determines if contact info is visible.
Current Tech: Bootstrap 5, MySQL/SQLite, Django Templates.


I am building a Matrimonial Website using Python/Django and MySQL.
Structure: Modular (Apps: users, search, payments, communications).
Key Features: Multi-language (Eng/Hindi toggle), Paywall for contact sharing, Admin panel for manual approval.
Current Status: successfully built the Core Infrastructure of a professional web application. Here is exactly what is completed:
1. The "Brain" (Backend Configuration)
Django Project (core): Fully configured with 4 custom apps (users, search, payments, communications).
Third-Party Integration: django-crispy-forms installed and configured for "Smooth" Bootstrap 5 styling.
Media/Static Setup: Ready to handle CSS and (soon) user photos.
2. The Database (The "Legit" Models)
Custom User Table: Handles high-security login plus full_name, occupation, and the is_paid paywall switch.
Profile Table: A separate "Bio-Data" table linked 1-to-1 with the user (The Pro Way).
Automation: Django Signals are active—whenever a user registers, a Profile row is automatically created in the background.
3. The "Logic Gate" (Business Model)
Functional Paywall: Code that checks if user.is_paid and hides/shows sensitive info (Father’s name, Hometown) based on that status.
Access Control: Different views for Guests (Register), Free Users (Upgrade), and Paid Users (Full Bio).
4. The "Skin" (Frontend Templates)
Master Shell (base.html): Global navigation, Bootstrap CDN, and legal disclaimer in the footer.
Home Page (home.html): Professional landing page with a call-to-action button.
Profile List: Professional "Cards" layout showing available matches.
Contact Page: The manual bridge for payments.
5. User Journey (Auth)
Registration: A "Smooth" styled form that creates real users in your database.
Login/Logout: Secure, battle-tested system using Django's internal auth views.
Admin Panel: A fully customized dashboard where your father can manage users and check/uncheck the "Paid" status.

Tech Debt to Avoid: Do not use raw SQL (use ORM), No hardcoded secrets (use .env), must be mobile-responsive.

Every single time you add a feature, you will change these three things:
views.py: To tell Python which HTML file to use.
urls.py: To give that page a web address (and a name).
The HTML (base.html or others): To add the link using the {% url 'name' %} tag.

MarriageSite/
├── manage.py
├── db.sqlite3
├── .env
├── requirements.txt
├── venv/
├── static/
├── media/
├── core/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
|   ___ asgi.py
├── templates/
│   ├── base.html
│   └── users/
│       ├── 
│       ├── profile_list.html
│       ├── register.html
│       ├── login.html
│       └── contact.html
├── users/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py
│   ├── tests.py
│   ├── urls.py
│   ├── views.py
│   └── migrations/
├── search/
├── payments/
└── communications/
