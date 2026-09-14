# Multi-Tenant Course/LMS SaaS Platform

Built with **Django**, **HTMX**, **Tailwind CSS**, and **Alpine.js**.

## 📖 Complete Documentation & Guide
Please read the comprehensive guide in [`saascourse/PROJECT_GUIDE.md`](./saascourse/PROJECT_GUIDE.md) for full architecture details, template breakdown, models, and usage instructions in Bengali and English.

---

## ⚡ Quick Start

```powershell
# Navigate into the Django project directory
cd E:\saascourse\saascourse

# Run the development server on port 8001
.\venv\Scripts\python.exe manage.py runserver 8001
```

### 🌐 Access URLs:
- **Main SaaS Landing Page:** [http://localhost:8001/](http://localhost:8001/)
- **Tenant 1 (Alpha Academy):**
  - Frontend Catalog: [http://alpha.localhost:8001/](http://alpha.localhost:8001/)
  - Backend Instructor Studio: [http://alpha.localhost:8001/courses/manage/dashboard/](http://alpha.localhost:8001/courses/manage/dashboard/)
  - Academy Settings & SMS Gateway: [http://alpha.localhost:8001/tenants/settings/](http://alpha.localhost:8001/tenants/settings/)
- **Tenant 2 (Design Masterclass):**
  - Frontend Catalog: [http://beta.localhost:8001/](http://beta.localhost:8001/)
  - Backend Instructor Studio: [http://beta.localhost:8001/courses/manage/dashboard/](http://beta.localhost:8001/courses/manage/dashboard/)
  - Academy Settings & SMS Gateway: [http://beta.localhost:8001/tenants/settings/](http://beta.localhost:8001/tenants/settings/)
- **Admin Portal:** [http://localhost:8001/admin/](http://localhost:8001/admin/) (`admin@platform.com` / `admin123`)

---

## ⚙️ Main Domain & Coaching Center Settings

### 1. Changing the Admin Main Domain:
Set the environment variable or edit `saascourse/settings.py`:
```python
PLATFORM_MAIN_DOMAIN = "yourdomain.com" # Default: "platform.com"
```
The superadmin portal is directly at `https://yourdomain.com/admin/`. Subdomains automatically route to `[tenant].yourdomain.com`.

### 2. Coaching Center Brand Assets (Logo, Banner, Favicon) & SMS Gateway:
- **Superadmin (All Academies):** Manage any coaching center's logo, hero banner, favicon, and SMS credentials in Django Admin: [http://localhost:8001/admin/tenants/tenant/](http://localhost:8001/admin/tenants/tenant/)
- **Academy Owners:** Manage visual branding and SMS gateways directly at `/tenants/settings/?tab=branding` and `/tenants/settings/?tab=sms`.
- **Supported SMS Gateways:** SSL Wireless, Greenweb SMS, MimSMS, Twilio, and Generic HTTP API with live interactive testing tool.
