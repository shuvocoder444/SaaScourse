# Multi-Tenant Course/LMS SaaS Platform — সম্পূর্ণ গাইড ও আর্কিটেকচার বুকলেট

এই প্ল্যাটফর্মটি একটি **B2B Course SaaS (যেমন: Teachable / Kajabi)** মডেল অনুযায়ী তৈরি করা হয়েছে। 

এখানে দুটি স্তর রয়েছে:
1. **প্ল্যাটফর্ম অ্যাডমিন লেভেল (`localhost:8001` বা `saascourse.com`):**  
   অ্যাডমিন নিজে কোনো কোর্স বিক্রি করবে না, অ্যাডমিন মূলত **সাসপশন প্ল্যান (Starter, Pro, Enterprise)** বিক্রি করবে। এখানে প্ল্যাটফর্মের চমৎকার সেলস ল্যান্ডিং পেজ এবং নতুন ক্রিয়েটরদের জন্য সেলফ-সার্ভিস অনবোর্ডিং সাইনআপ উইজার্ড রয়েছে।
2. **ক্রিয়েটর / অ্যাকাডেমি টেন্যান্ট লেভেল (`[slug].localhost:8001` বা কাস্টম CNAME ডোমেন):**  
   যারা এই প্ল্যাটফর্মে অ্যাকাউন্ট খুলবে, তারা তাদের নিজস্ব আলাদা ব্র্যান্ডেড **অ্যাকাডেমি ল্যান্ডিং পেজ (স্টোরফ্রন্ট)** পাবে। তারা তাদের নিজস্ব থিম কালার, লোগো, হিরো ব্যানার সাজিয়ে নিজস্ব কোর্স ও ভিডিও লেসন আপলোড ও বিক্রি করবে।

---

## ১. ডুয়াল ল্যান্ডিং পেজ আর্কিটেকচার (Dual Landing System)

```
                            ভিজিটর রিকোয়েস্ট
                                   │
                                   ▼
                 ┌───────────────────────────────────┐
                 │    TenantResolutionMiddleware     │
                 └─────────────────┬─────────────────┘
                                   │
                ┌──────────────────┴──────────────────┐
                ▼                                     ▼
   [মেইন প্ল্যাটফর্ম ডোমেন]                [টেন্যান্ট সাবডোমেন/CNAME]
    (e.g., localhost:8001)                (e.g., alpha.localhost:8001)
                │                                     │
                ▼                                     ▼
   ┌───────────────────────────┐         ┌───────────────────────────┐
   │ প্ল্যাটফর্ম SaaS সেলস পেজ │         │ ক্রিয়েটরের অ্যাকাডেমি     │
   │ (tenants/platform_home)   │         │ ল্যান্ডিং পেজ (স্টোরফ্রন্ট)│
   │ - SaaS ফিচার ও ভ্যালু     │         │ (courses/frontend/academy)│
   │ - সাবস্ক্রিপশন প্ল্যানসমূহ │         │ - কাস্টম ব্র্যান্ড কালার  │
   │   (Starter, Pro, Ent)     │         │ - নিজস্ব হিরো হেডলাইন     │
   │ - "Start Free Trial" বাটন │         │ - ফিচার্ড কোর্স ক্যাটালগ  │
   │   -> /signup/ রেজিস্ট্রেশন│         │ - কারিকুলাম ও লেসন প্লেয়ার│
   └───────────────────────────┘         └───────────────────────────┘
```

---

## ২. ফোল্ডার ও টেমপ্লেট স্ট্রাকচার

```text
E:\saascourse\
├── venv/                                   # পাইথন ভার্চুয়াল এনভায়রনমেন্ট
└── saascourse/                             # মূল প্রজেক্ট রুট
    ├── manage.py                           # জ্যাঙ্গো ম্যানেজমেন্ট কমান্ড
    ├── db.sqlite3                          # ডেটাবেস
    │
    ├── core/                               # মাল্টি-টেন্যান্সি কোর ইঞ্জিন
    │   └── tenancy/
    │       ├── context.py                  # Thread-safe contextvars স্টোরেজ
    │       ├── models.py                   # TenantAwareModel & TenantManager
    │       ├── middleware.py               # সাব-ডোমেন ও CNAME রেজোলিউশন মিডলওয়্যার
    │       └── tests.py                    # অটোমেটেড আইসোলেশন ও সাবস্ক্রিপশন টেস্ট
    │
    ├── apps/
    │   ├── tenants/                        # অ্যাকাডেমি ও সাবস্ক্রিপশন ইঞ্জিন
    │   │   ├── models.py                   # Tenant, SubscriptionPlan, TenantSubscription
    │   │   ├── views.py                    # platform_landing_view, tenant_registration_view, settings
    │   │   ├── urls.py                     # /signup/, /tenants/settings/
    │   │   ├── tests.py                    # সেলফ-সার্ভিস সাইনআপ ও স্টোরফ্রন্ট টেস্ট
    │   │   └── templates/tenants/
    │   │       ├── platform_home.html      # 🚀 অ্যাডমিনের SaaS সেলস ও প্রাইসিং ল্যান্ডিং পেজ
    │   │       ├── register.html           # 📝 নতুন অ্যাকাডেমি তৈরির অনবোর্ডিং ফর্ম (14-Day Trial)
    │   │       ├── settings.html           # 🎨 অ্যাকাডেমির থিম কালার ও ল্যান্ডিং পেজ এডিটর
    │   │       └── suspended.html          # সাময়িকভাবে বন্ধ অ্যাকাডেমির পেজ
    │   │
    │   ├── courses/                        # কোর্স ও এলএমএস ইঞ্জিন
    │   │   ├── models.py                   # Course, Module, Lesson, Enrollment, Progress
    │   │   ├── views.py                    # course_list, course_detail, lesson_view, instructor studio
    │   │   ├── urls.py                     # কোর্সের সমস্ত রাউটিং
    │   │   └── templates/courses/
    │   │       ├── frontend/               # 🎓 ছাত্র/লার্নারদের ফ্রন্টএন্ড স্টোরফ্রন্ট
    │   │       │   ├── academy_home.html   # ক্রিয়েটরের নিজস্ব ল্যান্ডিং পেজ
    │   │       │   ├── list.html           # ফুল কোর্স ক্যাটালগ
    │   │       │   ├── detail.html         # কোর্স কারিকুলাম ও সিলেবাস
    │   │       │   └── lesson.html         # ভিডিও ও রিডিং লেসন প্লেয়ার (HTMX টগল)
    │   │       └── backend/                # 🛠️ ইন্সট্রাক্টর স্টুডিও ড্যাশবোর্ড
    │   │           └── dashboard.html      # কোর্স ম্যানেজমেন্ট, সাবস্ক্রিপশন স্ট্যাটাস
    │   │
    │   └── users/                          # কাস্টম ইউজার ও মেম্বারশিপ
    │       ├── models.py                   # Custom User (Email auth) & TenantMembership
    │       └── templates/users/
    │           └── profile.html            # ইউজার প্রোফাইল ও অ্যাকাডেমি মেম্বারশিপ পেজ
    │
    └── templates/
        └── base.html                       # গ্লোবাল মাস্টার লেআউট (Tailwind + Alpine + HTMX)
```

---

## ৩. সাবস্ক্রিপশন প্ল্যান ও অনবোর্ডিং ফ্লো

### ৩টি সাবস্ক্রিপশন টিয়ার:
1. **Starter Plan ($29/mo):**
   - সর্বোচ্চ ৫টি প্রকাশিত কোর্স।
   - ২৫০ জন শিক্ষার্থী।
   - কাস্টম সাবডোমেন (`[brand].platform`).
2. **Professional Plan ($79/mo - Most Popular):**
   - সর্বোচ্চ ২৫টি প্রকাশিত কোর্স।
   - ২,৫০০ শিক্ষার্থী।
   - নিজস্ব হোয়াইট-লেবেল CNAME কাস্টম ডোমেন (`learn.mycompany.com`).
   - কাস্টম কালার ও থিম ব্র্যান্ডিং।
3. **Enterprise Plan ($199/mo):**
   - ১০০টি প্রকাশিত কোর্স।
   - ১০,০০০ শিক্ষার্থী।
   - মাল্টি-ইন্সট্রাক্টর সাপোর্ট ও ডেডিকেটেড সাপোর্ট।

### সেলফ-সার্ভিস অনবোর্ডিং ফ্লো (`/signup/`):
1. নতুন ব্যবহারকারী মেইন সাইট (`http://localhost:8001/`) থেকে যেকোনো প্ল্যানের নিচে **"Start 14-Day Free Trial"**-এ ক্লিক করবে।
2. রেজিস্ট্রেশন ফর্মে তার নাম, ইমেইল, পাসওয়ার্ড, অ্যাকাডেমির নাম এবং কাঙ্ক্ষিত সাবডোমেন প্রদান করবে।
3. জ্যাঙ্গো সাথে সাথে:
   - ইউজার তৈরি করবে।
   - টেন্যান্ট ডেটাবেসে যুক্ত করবে।
   - ১৪ দিনের ফ্রি ট্রায়াল সাবস্ক্রিপশন অ্যাক্টিভ করবে।
   - তাকে অ্যাকাডেমির অ্যাডমিন মেম্বারশিপ দিয়ে স্বয়ংক্রিয়ভাবে লগইন করাবে।
4. তাকে সরাসরি তার নতুন অ্যাকাডেমির ইন্সট্রাক্টর স্টুডিওতে রিডাইরেক্ট করে দেবে (`http://[subdomain].localhost:8001/courses/manage/dashboard/`)।

---

## ৪. লাইভ টেস্ট লিঙ্কসমূহ (Port 8001-এ রানিং)

- **মেইন প্ল্যাটফর্ম SaaS ল্যান্ডিং পেজ (অ্যাডমিন যা বিক্রি করবে):**  
  [http://localhost:8001/](http://localhost:8001/)
- **ক্রিয়েটর অনবোর্ডিং উইজার্ড (ফ্রি ট্রায়াল সাইনআপ):**  
  [http://localhost:8001/signup/](http://localhost:8001/signup/)

- **অ্যাকাডেমি ১ (Alpha Code Academy - ক্রিয়েটরের নিজস্ব ল্যান্ডিং পেজ):**  
  - নিজস্ব স্টোরফ্রন্ট: [http://alpha.localhost:8001/](http://alpha.localhost:8001/)  
  - ইন্সট্রাক্টর স্টুডিও ও সাবস্ক্রিপশন মেট্রিক্স: [http://alpha.localhost:8001/courses/manage/dashboard/](http://alpha.localhost:8001/courses/manage/dashboard/)  
  - ল্যান্ডিং পেজ ও থিম কালার এডিটর: [http://alpha.localhost:8001/tenants/settings/](http://alpha.localhost:8001/tenants/settings/)

- **অ্যাকাডেমি ২ (Design Masterclass - ক্রিয়েটরের নিজস্ব ল্যান্ডিং পেজ):**  
  - নিজস্ব স্টোরফ্রন্ট: [http://beta.localhost:8001/](http://beta.localhost:8001/)  
  - ইন্সট্রাক্টর স্টুডিও: [http://beta.localhost:8001/courses/manage/dashboard/](http://beta.localhost:8001/courses/manage/dashboard/)

- **জ্যাঙ্গো সুপারঅ্যাডমিন প্যানেল:**  
  [http://localhost:8001/admin/](http://localhost:8001/admin/)  
  *(Login: `admin@platform.com` / `admin123`)*

---

## ৫. দরকারি কমান্ডসমূহ

- **সার্ভার রান করা:**
  ```powershell
  cd E:\saascourse\saascourse
  & ..\venv\Scripts\python.exe manage.py runserver 8001
  ```
- **টেস্ট রান করা (২৩টি ইউনিট টেস্টের সবগুলো পাস):**
  ```powershell
  & ..\venv\Scripts\python.exe manage.py test
  ```
- **ডেমো ডেটা ও সাবস্ক্রিপশন সিড করা:**
  ```powershell
  & ..\venv\Scripts\python.exe manage.py seed_demo_data
  ```

---

## ৬. কোর্স প্লেয়ার ও কারিকুলাম ট্র্যাকার (Course Player & Curriculum Tracker)

কোর্স প্লেয়ারটি **Django + HTMX + Tailwind CSS + Alpine.js** দিয়ে তৈরি করা হয়েছে যা সম্পূর্ণ SPA (Single Page Application)-এর মতো মসৃণ অভিজ্ঞতা দেয়:

```
┌───────────────────────────────┬─────────────────────────────────────────────────────────┐
│       SIDEBAR (Alpine.js)     │               MAIN CONTENT AREA (#player-main-content)   │
├───────────────────────────────┼─────────────────────────────────────────────────────────┤
│ 🔙 Back to Course             │  [🎥 16:9 Responsive Video Player / Markdown Text]      │
│                               │                                                         │
│ 📊 Curriculum Progress:       │  Module 1 > Lesson 1                                    │
│ [████████████░░░░░░] 67%      │  Lesson Title & Complete Toggle Button                  │
│                               │                                                         │
│ ▼ Module 1 (Accordion)        │  Lesson Content / Article Text                          │
│   [✓] 1. Setting up Django    │                                                         │
│   [✓] 2. Multi-Tenant Model   │  ─────────────────────────────────────────────────────  │
│                               │  [← Previous Lesson]             [Complete & Next →]    │
│ ▶ Module 2 (Accordion)        │                                                         │
│   [ ] 3. HTMX State Swaps     │  (Clicking 'Complete & Next' sends HTMX POST,           │
│   [ ] 4. Production Caddy     │   swaps player content, updates progress bar & check)   │
└───────────────────────────────┴─────────────────────────────────────────────────────────┘
```

### প্রধান ফিচারসমূহ:
1. **বাম পাশের কোল্যাপসিবল সাইডবার (Collapsible Sidebar):**
   - Alpine.js পরিচালিত (`x-data="{ sidebarOpen: true }"`) এবং মোবাইল ভিউতে স্লাইড-ইন ড্রয়ার।
   - অ্যাকর্ডিয়ন স্টাইলে মডিউল ও লেসন তালিকা।
   - প্রতি লেসনের পাশে ডায়নামিক কমপ্লিশন টিকমার্ক (`#lesson-check-{{ lesson.id }}`).
2. **আউট-অব-ব্যান্ড সোয়াপ (`hx-swap-oob="true"`):**
   - যখন শিক্ষার্থী **"Complete & Next Lesson →"** বাটনে ক্লিক করে, ব্যাকএন্ডে `LessonProgress` সেভ হয়।
   - পুরো পেজ রিলোড না করে শুধুমাত্র মেইন ভিডিও/কনটেন্ট এলাকা নতুন লেসনে পরিবর্তিত হয় (`hx-target="#player-main-content"`).
   - একই সাথে রেসপন্সে পাঠানো `hx-swap-oob="true"` এর মাধ্যমে সাইডবারের প্রগ্রেস বার শতাংশ এবং সংশ্লিষ্ট লেসনের চেকমার্ক রিয়েল-টাইমে সবুজ হয়ে যায়।
   - ব্রাউজারের URL স্বয়ংক্রিয়ভাবে আপডেট হয় (`HX-Push-Url` হেডারের মাধ্যমে)।
3. **কোর্স সমাপ্তির সেলিব্রেশন:**
   - শেষ লেসনটি সম্পন্ন হলে স্বয়ংক্রিয়ভাবে একটি আকর্ষণীয় "Congratulations! Course Completed" স্ক্রিন শো করে।

---

## ৭. কাস্টম ডোমেন ভেরিফিকেশন ও জিরো-টাচ ডায়নামিক SSL (Custom Domain & Dynamic SSL)

প্রফেশনাল ও এন্টারপ্রাইজ প্ল্যানের গ্রাহকরা তাদের নিজস্ব ব্র্যান্ডেড ডোমেন (যেমন: `learn.myacademy.com`) CNAME রেকর্ডের মাধ্যমে ম্যাপ করতে পারে।

### কীভাবে কাজ করে:

```
                                 কাস্টমার ডোমেন: learn.myacademy.com
                                                │
                                    (DNS CNAME বা TXT Challenge)
                                                │
                                                ▼
                                    [Caddy Web Server / Reverse Proxy]
                                                │
                                                ▼ (TLS Handshake আসার পর)
                                       GET /tenants/api/caddy-check/?domain=learn.myacademy.com
                                                │
                             ┌──────────────────┴──────────────────┐
                             │                                     │
                        (200 OK)                              (400 Bad Request)
                             │                                     │
                             ▼                                     ▼
             [স্বয়ংক্রিয় Let's Encrypt / ZeroSSL]        [হ্যান্ডশেক বাতিল (DoS অ্যাটাক প্রতিরোধ)]
             সার্টিফিকেট তৈরি ও ব্রাউজারে সুরক্ষিত লোড
```

1. **DNS ভেরিফিকেশন ব্যাকএন্ড (`apps/tenants/views.py`):**
   - প্রতিটি টেন্যান্টের জন্য একটি ক্রিপ্টোগ্রাফিক ভেরিফিকেশন টোকেন জেনারেট হয় (যেমন: `saas-verify-a1b2c3d4...`)।
   - ব্যবহারকারী তাদের DNS ম্যানেজারে দুটি রেকর্ড যুক্ত করবে:
     - **CNAME:** `learn.myacademy.com` -> `cname.platform.com`
     - **TXT:** `_saascourse-challenge.learn.myacademy.com` -> `saas-verify-a1b2c3...`
   - সেটিংসে **"Verify DNS Records Now"** বাটনে ক্লিক করলে পাইথনের `dns.resolver` দিয়ে স্বয়ংক্রিয়ভাবে রেকর্ড টেস্ট করা হয়।
2. **Caddy On-Demand TLS (`deploy/Caddyfile`):**
   - ক্লাউডে কোনো ম্যানুয়াল Certbot চালানো বা Nginx রিলোড দেওয়ার প্রয়োজন নেই।
   - কাস্টমার যখন প্রথমবার `https://learn.myacademy.com` ভিজিট করে, Caddy জ্যাঙ্গোর সিকিউরিটি এন্ডপয়েন্ট `/tenants/api/caddy-check/?domain=...` কল করে।
   - জ্যাঙ্গো নিশ্চিত করে যে ডোমেনটি সিস্টেমে ভেরিফাইড ও অ্যাক্টিভ। Caddy সাথে সাথে অন-দ্য-ফ্লাই SSL সার্টিফিকেট ইস্যু করে।
   - কোনো হ্যাকার রেন্ডম ডোমেন পয়েন্ট করে SSL লিমিট শেষ বা DoS করতে পারবে না।
3. **প্রোডাকশন কনফিগারেশন ফাইলসমূহ:**
   - `deploy/Caddyfile`: জিরো-টাচ অন-ডিমান্ড TLS রিভার্স প্রক্সি কনফিগারেশন।
   - `deploy/nginx.conf`: Nginx + Cloudflare for SaaS রিভার্স প্রক্সি কনফিগারেশন।

---

## ৮. সবার জন্য আলাদা ড্যাশবোর্ড (Role-Based Dashboards for Everyone)

প্ল্যাটফর্মে ৩টি ভিন্ন ব্যবহারকারী রোলের জন্য আলাদা আলাদা প্রিমিয়াম ড্যাশবোর্ড এবং একটি স্মার্ট ইউনিভার্সাল রাউটার (`/dashboard/`) রয়েছে:

### ১. 👑 প্ল্যাটফর্ম ওনার / সুপারঅ্যাডমিন ড্যাশবোর্ড (SaaS Executive Dashboard)
- **অ্যাক্সেস URL:** [http://localhost:8001/dashboard/](http://localhost:8001/dashboard/) (যখন `admin@platform.com` দিয়ে রুট ডোমেনে লগইন করা হয়)।
- **ফিচারসমূহ:**
  - পুরো SaaS বিজনেসের **MRR ($ Monthly Recurring Revenue)** রিয়েল-টাইম ক্যালকুলেশন।
  - মোট অ্যাক্টিভ অ্যাকাডেমি, ১৪ দিনের ফ্রি ট্রায়াল গ্রাহক ও স্থগিত অ্যাকাডেমির সংখ্যা।
  - সাবস্ক্রিপশন প্ল্যান ডিস্ট্রিবিউশন (Starter $29, Pro $79, Enterprise $199)।
  - সব অ্যাকাডেমির ডিরেক্টরি টেবিল (মালিকের ইমেইল, কাস্টম CNAME ডোমেন ভেরিফিকেশন স্ট্যাটাস, এবং সরাসরি অ্যাকাডেমির স্টুডিও/স্টোরফ্রন্টে ঢোকার লিঙ্ক)।

### ২. 🎓 অ্যাকাডেমি ক্রিয়েটর / ইন্সট্রাক্টর স্টুডিও (Instructor Studio Dashboard)
- **অ্যাক্সেস URL:** [http://alpha.localhost:8001/dashboard/](http://alpha.localhost:8001/dashboard/) (যখন ক্রিয়েটর তার নিজস্ব অ্যাকাডেমি সাবডোমেনে লগইন করে)।
- **ফিচারসমূহ:**
  - **সাবস্ক্রিপশন কোটা মিটার:** প্ল্যান অনুযায়ী কয়টি কোর্স ব্যবহৃত হয়েছে (যেমন: `২ / ২৫ কোর্স ব্যবহৃত (Pro Plan)` এবং প্রগ্রেস বার)।
  - মোট কারিকুলাম মডিউল, লেসন সংখ্যা এবং সক্রিয় স্টুডেন্ট এনরোলমেন্ট মেট্রিক্স।
  - কোর্সের ড্রাফট ও পাবলিশড কাউন্টার এবং সরাসরি কোর্স এডিটর লিঙ্ক।
  - কাস্টম ডোমেন স্ট্যাটাস কার্ড ও ব্র্যান্ডিং/থিম সেটিংস লিঙ্ক।

### ৩. 📚 শিক্ষার্থী / লার্নার ড্যাশবোর্ড (Student Learning Dashboard)
- **অ্যাক্সেস URL:** [http://alpha.localhost:8001/dashboard/](http://alpha.localhost:8001/dashboard/) (যখন শিক্ষার্থী `alex@student.com` অ্যাকাডেমি সাবডোমেনে লগইন করে)।
- **ফিচারসমূহ:**
  - শিক্ষার্থীর এনরোল করা কোর্সের তালিকা এবং লাইভ পার্সেন্টেজ প্রগ্রেস বার (যেমন: `৬৭% সম্পন্ন, ৪/৬ লেসন`)।
  - বুদ্ধিমান **"Resume Learning →"** বাটন: যা ক্লিক করলেই সরাসরি কোর্স প্লেয়ারে শিক্ষার্থীর সর্বশেষ অসম্পন্ন লেসনে নিয়ে যায়।
  - কোর্স সম্পন্ন হলে "🎉 Completed" সেলিব্রেশন ব্যাজ।
  - অ্যাকাডেমির অন্যান্য কোর্স এক্সপ্লোর করার সেকশন।

### ৪. ⚡ ১-ক্লিক ডেমো লগইন ও স্মার্ট রাউটিং (`/login/` ও `/dashboard/`)
- **লগইন পোর্টাল:** [http://localhost:8001/login/](http://localhost:8001/login/)
  - পাসওয়ার্ড না লিখে তাৎক্ষণিকভাবে টেস্ট করার জন্য রয়েছে ৩টি ১-ক্লিক বাটন:
    - 👑 **Platform SuperAdmin** (`admin@platform.com`)
    - 🎓 **Academy Creator** (`sarah@alpha.io`)
    - 📚 **Student / Learner** (`alex@student.com`)
  - যে কেউ যেখান থেকেই `/dashboard/` ভিজিট করুক না কেন, সিস্টেম স্বয়ংক্রিয়ভাবে তার রোল ও টেন্যান্ট কনটেক্সট শনাক্ত করে সঠিক ড্যাশবোর্ডে পৌঁছে দেয়।


