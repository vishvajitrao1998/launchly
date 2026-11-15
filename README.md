# Launchly: a Django SaaS launch platform

Product-Hunt-style platform: makers submit products, admins review them, the community upvotes and likes,
and advertisers buy paid slots. Payments via Razorpay, data in MySQL.

## Quick start

```bash
# 1. MySQL
mysql -u root -p -e "CREATE DATABASE launchly CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 2. Python env
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt                         # mysqlclient needs libmysqlclient-dev / mysql-connector (see below)

# 3. Config
cp .env.example .env     # fill DB_*, RAZORPAY_*, SITE_URL

# 4. Database + demo data
python manage.py makemigrations core
python manage.py migrate
python manage.py seed                 # categories, plans, demo products
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000 · Django admin at `/admin/` · staff review queue at `/review/`.

> `mysqlclient` on Ubuntu: `sudo apt install pkg-config default-libmysqlclient-dev build-essential`.
> No MySQL handy? Set `DB_ENGINE=sqlite` in `.env` for a quick smoke test.

## How each requirement is implemented

| Requirement | Where |
|---|---|
| Dark mode | `data-theme` on `<html>`, CSS variables in `static/css/app.css`, inline head script prevents flash, choice saved in localStorage, follows OS by default |
| Templates render only, API fills data | Every page in `templates/` is a static shell. `static/js/pages.js` calls `/api/...` and renders with skeleton loaders. Home needs a single call: `/api/feed/` |
| Collapsible sidebar (icons only + animation) | `.sidebar` width/labels animate with CSS transitions; state persisted; becomes a drawer on mobile |
| Admin approve / reject / email maker | `/review/` page (+ Django admin actions). Actions: **approve**, **reject**, **request info** (sets status *Needs info*, emails the maker, shows the note on their dashboard, lets them fix & resubmit), **email only**. Logic in `core/services.py:review_product` |
| Schedule a launch | Submit form has "Launch when approved" or "Schedule". On approval `launch_at = max(now, scheduled_for)`. Public queries use `Product.objects.live()` (`status=approved AND launch_at <= now`), so scheduled products appear on their own, no cron needed |
| Home page: apps + categories + animation | `/` with category chips, per-category lists, "Just launched" |
| Reserved ad places + slot board | Hero banner and 3 Spotlight tiles on Home; "Advertising slots" board shows which slot is booked for the next 4 weeks (`/api/ads/board/`) |
| 1st & 3rd positions paid per category | `/api/feed/` builds each category as `[slot#1, app, slot#3, app, app...]`. A booked slot always shows its advertiser however many apps the category has; free ones show a "Your app here" CTA |
| Pricing + Razorpay | `/pricing/` plans (DB-driven) and ad-slot prices (per week, `AD_PRICING_INR` in settings). Flow: create order → Razorpay Checkout → signature verify (`/api/payments/verify/`) → webhook as safety net |
| Different price for ad slots | Plans = monthly subscription with Premium credits. Ad slots = per-week price by slot type |
| Like & upvote | Toggle endpoints with unique constraints and denormalised counters |
| Submit a product | `/submit/` with name, tagline, description, URL, logo, category, schedule, premium |
| Premium badge | `Product.is_premium`; consuming a plan credit on submit; gold shimmering badge and gold card border; credit refunded if rejected |
| Font / colours | Plus Jakarta Sans; indigo→violet brand on cool slate; gold reserved for Premium |

## Razorpay setup
1. Dashboard → Settings → API Keys → generate **test** keys → put in `.env`.
2. Webhooks (needed for production reliability): URL `https://YOUR_DOMAIN/razorpay/webhook/`,
   events `payment.captured`, `order.paid`, secret = `RAZORPAY_WEBHOOK_SECRET`.
3. Test card: any Razorpay test card / UPI `success@razorpay`.

Plans are sold as one-time 30-day purchases (simple and robust). For auto-renewal, swap in Razorpay Subscriptions.

## Email
Default backend prints emails to the terminal. For real mail set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` and the SMTP vars.

## API cheat-sheet
```
GET  /api/feed/  /api/categories/  /api/products/?q=&category=&sort=  /api/products/<slug>/
GET  /api/ads/board/   /api/pricing/   /api/me/
POST /api/products/<id>/upvote/   /api/products/<id>/like/
GET|POST /api/me/products/   GET|PATCH /api/me/products/<id>/   GET /api/me/ads/
POST /api/payments/plan/  /api/payments/ad/  /api/payments/verify/
GET  /api/admin/queue/?status=   POST /api/admin/products/<id>/review/  {action, message}
```

## Before production
- `DJANGO_DEBUG=0`, strong `DJANGO_SECRET_KEY`, real `ALLOWED_HOSTS`, `SITE_URL`, HTTPS.
- `python manage.py collectstatic`, run with gunicorn; serve `/media/` from nginx or S3.
- Ad booking double-spend: `slot_taken()` is checked before payment and unpaid holds last 15 min. For very high traffic add a DB lock around booking.
- Cache `/api/feed/` (e.g. 30-60 s) for anonymous users if traffic grows.
