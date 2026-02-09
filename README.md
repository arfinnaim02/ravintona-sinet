🍕 Ravintola Sinet – Restaurant Website & Reservation System

A premium, server-rendered restaurant website for Ravintola Sinet (Joensuu, Finland) with a custom reservation system, menu management, and admin dashboard.

Built with Django + Tailwind CSS, focused on performance, clarity, and maintainability — no frontend frameworks, no Django admin UI.

✨ Features
🌐 Public Website

Elegant homepage with featured dishes

Category-based menu with tags (vegan, popular, spicy, etc.)

Menu item modal popup with Add to Table (pre-order)

Table reservation system with:

30-minute time slots

Capacity enforcement

Optional food pre-ordering

Premium UI with rustic / gold / wood theme

Fully responsive (desktop-first)

🪑 Reservation System

Fixed 30-minute booking intervals

Capacity rules (per time slot):

14 tables

55 chairs

2 baby seats

Automatic table calculation

Optional food pre-order saved with reservation

Strict validation at model level

🛠️ Custom Admin Panel (No Django Admin)

Secure admin login

Dashboard overview:

Total reservations

Pending / upcoming reservations

Menu statistics

Manage:

Reservations (status updates)

Menu items

Categories

Clean sidebar navigation

Designed to match the restaurant’s premium branding

🧱 Tech Stack
Layer	Technology
Backend	Python Django
Templates	Django Templates
Styling	Tailwind CSS (CDN)
Database	SQLite (dev)
Auth	Django Authentication
Frontend JS	Minimal vanilla JS
Admin UI	Custom-built (not Django admin)
📁 Project Structure
Ravintola-sinet.fi/
├── config/                 # Django project config
├── restaurant/             # Main application
│   ├── models.py           # Menu, Reservation, Preorder logic
│   ├── views.py            # Public + admin views
│   ├── forms.py            # Reservation + admin forms
│   ├── urls.py
│   └── templates/
│       ├── base.html
│       ├── home.html
│       ├── menu.html
│       ├── reservation.html
│       ├── partials/
│       │   └── menu_item_modal.html
│       └── admin/
│           ├── base.html
│           ├── dashboard.html
│           ├── reservations.html
│           └── ...
├── static/
│   └── images/
│       ├── logo/logo.jpg
│       └── admin/
├── media/
│   └── menu_items/
├── manage.py
└── db.sqlite3

🚀 Getting Started (Development)
1️⃣ Clone the Project
git clone https://github.com/yourusername/ravintola-sinet.git
cd Ravintola-sinet.fi

2️⃣ Create Virtual Environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

3️⃣ Install Dependencies
pip install -r requirements.txt

4️⃣ Run Migrations
python manage.py migrate

5️⃣ Create Admin User
python manage.py createsuperuser

6️⃣ Run Development Server
python manage.py runserver


Access:

Website → http://127.0.0.1:8000/

Admin panel → http://127.0.0.1:8000/admin/login/

🔐 Admin URLs
Feature	URL
Admin Login	/admin/login/
Dashboard	/admin/dashboard/
Menu Items	/admin/menu/
Categories	/admin/categories/
Reservations	/admin/reservations/
🧠 Design Philosophy

Server-rendered for speed and SEO

No frontend frameworks

Readable, maintainable code

Premium UI without JS bloat

Business logic enforced at model level

This project is designed to be:

Easy to extend

Easy to hand over

Easy for future AIs or developers to understand

🧩 Future Enhancements (Planned / Optional)

Online delivery checkout

Payment integration

Email/SMS reservation confirmations

Multi-language support (FI / EN)

Production database (PostgreSQL)

Docker deployment

📍 Restaurant Info

Ravintola Sinet
Joensuu, Finland
📞 +358 50 455 7367

📄 License

This project is proprietary and built specifically for Ravintola Sinet.