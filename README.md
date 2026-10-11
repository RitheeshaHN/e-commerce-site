# StepUp Shoes 👟

A complete, working shoe e-commerce website built with **Django 5** and vanilla
**HTML5 / CSS3 / JavaScript** (no front-end framework). Mobile-first and
responsive, with a full shopping flow from product browsing to order tracking.

---

## ✨ Features

### Storefront
- **Home page** — hero, category cards, featured picks, deals of the week, new arrivals
- **Product list** with pagination (12/page) and:
  - Filters: **category** (Men/Women/Kids + Running/Casual/Formal/Sports), **brand**,
    **price range** (min/max + quick buttons), **size (UK)**
  - **Search** by name / brand / description, with live navbar suggestions (JSON API)
  - **Sort** by newest, popularity, price ↑, price ↓, name
- **Product detail**
  - Image gallery (thumbnail switching), discount badge
  - Price, discount price, material, description, colour options
  - **Size selector with per-size stock** — out-of-stock sizes are disabled,
    low stock shows “Only N left”
  - Quantity stepper + **AJAX Add to Cart** (no page reload)
  - **Size guide modal** (UK → EU → foot length in cm)
  - **Reviews & star ratings** with a 5→1 distribution chart, one review per user
  - Related products section

### Cart
- Add / remove / update quantity **via `fetch()` — the page never reloads**
- **Guests**: cart stored in the session · **Logged-in users**: stored in the database
- **Guest cart is merged into the user cart on login *and* registration**
- Subtotal, shipping (free over ₹1,999), total, and a live **navbar cart badge**
- Quantities are always clamped to available stock (server-side)

### Orders
- Checkout with a validated shipping address form (server-side + client-side)
- Saved-address picker, “save this address to my profile” option
- **Payment: Cash on Delivery or a mock online-payment gateway**
  (Pay / Simulate failure buttons)
- Creates `Order` + `OrderItem` snapshots and **reduces stock atomically**
- Order confirmation page with a **status tracker**, order history, order detail
- **Cancel while Pending** — stock is automatically restored
- Statuses: `Pending → Confirmed → Shipped → Delivered`, plus `Cancelled`

### Accounts
- Register (auto-login + cart merge), login, logout, **password reset**
- Profile page: edit personal info, **saved address book** (add/edit/delete, one default)
- Checkout and order history are **login-protected**

### Admin (`/admin/`)
- Customized for catalog management: products with **inline sizes/stock and inline images**,
  categories (hierarchical), brands, reviews, carts, users, addresses
- Orders list with filters/search and **bulk actions**
  (Confirm / Ship / Deliver / Cancel — cancelling restores stock)

### Security & quality
- CSRF protection on every form and AJAX endpoint, server-side validation everywhere
- Hashed passwords (Django PBKDF2), login-protected views
- `SECRET_KEY` and `DEBUG` read from **environment variables** / `.env`
- Price math uses `DecimalField`; order rows store **snapshots** so history never drifts
- `select_for_update()` + `transaction.atomic()` prevent overselling
- 93 automated tests covering the whole flow

---

## 📁 Project structure

```
e-commerce site/
├── manage.py
├── requirements.txt
├── .env                    # SECRET_KEY, DEBUG (git-ignored)
├── .gitignore
├── README.md
├── stepup/                 # Django project (settings, urls, wsgi)
│   ├── settings.py         # env-var config, apps, DB, templates, static
│   └── urls.py             # root routing + password-reset views
├── accounts/               # custom User, Address, register/login/profile
│   ├── models.py  forms.py  views.py  urls.py  admin.py  tests.py
├── store/                  # catalog: Category, Brand, Product, images, sizes, reviews
│   ├── models.py  forms.py  views.py  urls.py  admin.py  tests.py
│   └── management/commands/seed_store.py   # ← sample data loader
├── cart/                   # Cart, CartItem, guest session cart, merge logic
│   ├── models.py  views.py  urls.py  utils.py  session.py
│   ├── context_processors.py  admin.py  tests.py
├── orders/                 # Order, OrderItem, checkout, cancel, mock payment
│   ├── models.py  forms.py  views.py  urls.py  admin.py  tests.py
├── templates/              # Django templates
│   ├── base.html  partials/  store/  cart/  orders/  accounts/
├── static/
│   ├── css/style.css       # mobile-first, no framework
│   └── js/main.js  cart.js # nav, toasts, search suggestions, AJAX cart
├── media/products/         # generated placeholder images
└── db.sqlite3
```

---

## 🚀 Setup (step by step)

> Requires **Python 3.11+** (tested on 3.12).

```bash
# 1. Clone the repository
git clone https://github.com/RitheeshaHN/e-commerce-site.git
cd "e-commerce site"

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
#    Copy `.env.example` values into a local `.env` (already provided), or set:
#      SECRET_KEY=<long-random-string>
#      DEBUG=True
#      ALLOWED_HOSTS=localhost,127.0.0.1
#    Generate one with:
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"

# 5. Apply database migrations (creates db.sqlite3)
python manage.py migrate

# 6. Create an admin login
python manage.py createsuperuser
#    Username: admin   (email + password of your choice)

# 7. Load sample data: 15 products, 16 categories, 6 brands,
#    sizes/stock, placeholder images, reviews, demo user
python manage.py seed_store
#    Add --wipe to reset the catalog first.

# 8. Run the development server
python manage.py runserver
```

Then open:

| URL | What |
|---|---|
| http://127.0.0.1:8000/ | Storefront |
| http://127.0.0.1:8000/admin/ | Admin panel |

**Seeded credentials**

| Account | Username | Password |
|---|---|---|
| Demo shopper | `demo` | `demo12345` |
| Admin | `admin` | *(the one you set in step 6)* |

---

## 🧪 Testing the full flow

1. **Register** → `Sign up` in the navbar (or use `demo` / `demo12345`).
   *Try it as a guest first: add an item to the cart, then register — the cart
   carries over.*
2. **Browse** → filter by *Men → Running*, switch the sort to *Price: low to high*,
   try the navbar search (“pegasus”).
3. **Open a product** → pick a size (out-of-stock sizes are disabled), check the
   📓 size guide, leave a review (rating stars), scroll to related products.
4. **Add to cart** → the navbar badge updates **without a reload**. On the cart
   page, use the +/− stepper or type a quantity — totals update instantly.
5. **Checkout** → fill the address (try an invalid PIN code first: `123` —
   server-side validation rejects it), choose **Cash on Delivery**, place the order.
6. **View the order** → confirmation page with the status tracker. Cancel it and
   watch the stock come back (check the product page’s size availability).
7. **Try online payment** → choose *Online payment*, then *Pay* on the mock
   gateway: the order becomes **Confirmed**. *Simulate failed payment* keeps it
   **Pending** so you can retry.
8. **Admin** → log in at `/admin/` → **Orders** → select orders and use the bulk
   actions to *Mark as Shipped*. Edit a product’s sizes/stock inline.

### Run the automated tests

```bash
python manage.py test          # all 93 tests
python manage.py test store    # one app: store | cart | orders | accounts
```

---

## 🔧 Switching to PostgreSQL later

`settings.py` keeps models portable (no SQLite-specific types). Change the
`DATABASES` block:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "stepup"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}
```

Then `pip install psycopg[binary]`, `python manage.py migrate`, and re-run
`python manage.py seed_store`.

---

## 📦 Production notes

Set `DEBUG=False` and provide a real `SECRET_KEY`. With `DEBUG=False`
`settings.py` automatically enables `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`,
`CSRF_COOKIE_SECURE` and HSTS. Also serve static files with a real web server:

```bash
python manage.py collectstatic
```

---

## 🛠 Tech stack

| Layer | Choice |
|---|---|
| Frontend | HTML5, CSS3 (mobile-first), vanilla JavaScript, Django templates |
| Backend | Django 5.2 (Python 3.11+) |
| Database | SQLite (default) → PostgreSQL-ready models |
| Images | Pillow (placeholder art generated by `seed_store`) |
