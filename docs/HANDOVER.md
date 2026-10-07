# Handover: Log Management Demo

สถานะ ณ 2026-10-02 · อ่านไฟล์นี้ก่อน แล้วค่อยอ่าน `docs/architecture.md`

## 1. โปรเจกต์นี้คืออะไร

งานทดสอบ Full-Stack Developer (Intern) ทำคนเดียว ส่งภายใน 10 วัน โจทย์คือสร้างระบบ log management ขนาดเล็ก (mini SIEM):
รับ log จากหลายแหล่ง → แปลงเป็น schema กลาง → เก็บและค้นหา → dashboard → alert
รันได้ 2 โหมดจาก Docker Compose ชุดเดียว คือ **Appliance** (VM เครื่องเดียว) และ **SaaS** (คลาวด์ มี HTTPS) และต้องแยกข้อมูลระหว่าง tenant

**แหล่งข้อมูลตามโจทย์ (7 ประเภท):** firewall, network (syslog), api, crowdstrike, aws, m365, ad
ต้องส่งข้อมูลเข้าระบบได้จริงอย่างน้อย 4 แหล่ง ส่วนที่เหลือใช้ไฟล์ตัวอย่างได้

**เกณฑ์คะแนน (100):** Ingestion 20 · Architecture & Docs 15 · Normalization 10 · Storage & Query 10 · Dashboard 10 · Alerting 10 · Security 10 · Deployment 10 · Tests & DX 5 · ผ่านที่ 60 · Strong Hire ที่ 85 ขึ้นไป และต้องอธิบายเหตุผลการออกแบบได้ · โบนัสสูงสุด +10 (multi-tenancy จริง, enrichment, CI/CD, IaC, observability)

Deliverables: repo (docs, compose, samples, backend/frontend/ingest พร้อม README, tests 2-3 เคส), วิดีโอ demo 30 นาที, URL SaaS หรือวิธีเปิด appliance, Postman collection

## 2. สถานะปัจจุบันแบบย่อ

| กลุ่ม | รายการ |
|---|---|
| **เสร็จและทดสอบแล้ว** (กับ Postgres 16 ที่ติดตั้งบน Ubuntu ไม่ใช่ผ่าน Docker) | schema แยก partition ต่อ tenant + RLS, role `log_app`, ฟังก์ชัน provision/retention ใน SQL, `db.py`, `policy.py`, syslog listener (UDP+TCP → batch → enrich → insert), enrichment (reverse DNS ทำงานจริง), pytest 16 ผ่าน |
| **เขียนแล้วแต่ยังไม่เคยรันจริง** | `docker-compose.yml` (6 service), Dockerfile, Caddyfile, GitHub Actions (`ci.yml`, `deploy.yml`), Terraform (AWS), `scripts/get_geoip.sh`, `worker.py` (retention), เอกสาร setup |
| **ยังไม่ได้ทำ** | normalizer ของ api/crowdstrike/aws/m365/ad, `POST /api/ingest` และอัปโหลดไฟล์, login/JWT + seed users, `/search`, `/stats/*`, alert engine, frontend (มีแค่หน้าเปล่า), `simulator.py`, Postman collection |

ตอนนี้ส่ง syslog เข้าระบบแล้วเก็บลง DB ได้ แต่ **ยังเปิดดูผ่าน UI หรือ API ไม่ได้** เพราะ API มีแค่ `/api/health`

## 3. สถาปัตยกรรมและเหตุผล

```
Syslog UDP/TCP (514) ─┐
POST /api/ingest ─────┼─► normalizers (ต่อแหล่ง) ─► enrich (GeoIP, reverse DNS) ─► PostgreSQL
File batch upload ────┘                                                              ▲   ▲
                                                          worker (alerts, retention) ┘   │
                                 React UI ◄── Caddy (HTTPS) ◄── API (JWT, RBAC, RLS) ────┘
```

**Container 6 ตัว:** `caddy` (ด่านหน้าเดียว 80/443), `frontend` (nginx), `api` (FastAPI), `ingest` (syslog listener), `worker`, `postgres` (ไม่เปิดพอร์ตออกนอก)
`api`, `ingest`, `worker` ใช้ **image Python เดียวกัน** (`Dockerfile` ที่ root) ต่างกันแค่ command เพื่อแชร์ `ingest/normalizers.py` โดยไม่ต้องคัดลอกโค้ด และเพื่อให้ API restart แล้ว syslog ไม่หลุด

**เหตุผลที่เลือก:**
- **PostgreSQL ตัวเดียว** (ไม่ใช้ OpenSearch): ดูแลระบบเดียว, partition ทำ retention ถูก, JSONB+GIN สำหรับฟิลด์เสริม, RLS แยก tenant ข้อเสียคือค้นข้อความอิสระใน `raw` สู้ OpenSearch ไม่ได้
- **Caddy**: ออก Let's Encrypt อัตโนมัติ และออก self-signed เมื่อ `DOMAIN=localhost` ทำให้ compose และ Caddyfile ชุดเดียวใช้ได้ทั้งสองโหมด
- **syslog รับที่พอร์ต 5514 ใน container** แล้ว map `514 → 5514` เพื่อไม่ต้องรันด้วยสิทธิ์ root
- **Tenant มาจาก JWT เท่านั้น** ไม่เชื่อ parameter จาก client

### โมเดล tenant (3 ชั้น)
1. **ตารางแยกจริง:** `events` เป็น `PARTITION BY LIST (tenant)` แล้วแต่ละ tenant แบ่งต่อเป็น `RANGE (ts)` รายวัน (`events_t_demoa_20261001`) retention = `DROP` partition รายวัน
2. **Row-Level Security:** API และ ingest เชื่อมต่อด้วย role `log_app` (ไม่ใช่ superuser, ไม่มี `BYPASSRLS`) ทุก transaction ตั้ง `app.tenant`/`app.is_admin` นโยบายเป็น fail-closed (ไม่ตั้ง = ไม่เห็นอะไร) `log_app` มีสิทธิ์เฉพาะตารางแม่ `events` จึงอ่าน partition ตรงๆ ไม่ได้
3. **API:** `app/policy.py` → `resolve_tenant()` (viewer ถูกล็อกที่ tenant ใน token, admin ส่ง `?tenant=` ได้) และ `filter_fields()` (viewer ไม่เห็น `raw` กับ `extra`)

**Role ฐานข้อมูล:** `log_app` ใช้โดย api และ ingest · owner (`POSTGRES_USER`) ใช้โดย worker เท่านั้น (ต้องทำ DDL สร้าง/ลบ partition)
**Tenant ต้อง provision ก่อนรับข้อมูล:** `SELECT provision_tenant('ชื่อ')` ข้อมูลของ tenant ที่ไม่มีอยู่จะ insert ไม่ผ่าน (ส่งข้อมูลมาเพื่อสร้าง tenant ไม่ได้)

## 4. โครงสร้างไฟล์

| Path | หน้าที่ | สถานะ |
|---|---|---|
| `docker-compose.yml`, `Dockerfile`, `.env.example`, `Makefile` | แพ็กเกจและคำสั่ง (`make up/down/logs/seed/test/geoip/reset`) | เขียนแล้ว ยังไม่เคยรัน |
| `caddy/Caddyfile` | `/api/*` → api, อื่นๆ → frontend, โดเมนจาก `DOMAIN` | เขียนแล้ว ยังไม่เคยรัน |
| `db/01_schema.sql` | ตาราง events/tenants/users/alert_rules/alerts, ฟังก์ชัน partition, RLS | **ทดสอบแล้ว** |
| `db/02_app_role.sh` | สร้าง `log_app` และ GRANT | **ทดสอบแล้ว** (จำลองการรัน ไม่ใช่ผ่าน entrypoint จริง) |
| `ingest/normalizers.py` | `normalize_syslog()` เสร็จ · ตัวอื่นเป็น TODO · `NORMALIZERS = {}` ว่าง | บางส่วน |
| `ingest/syslog_listener.py` | UDP+TCP → queue → batch 200/1 วินาที → normalize → enrich → insert | **ทดสอบแล้ว** |
| `ingest/enrich.py` | GeoIP (ไฟล์ออฟไลน์ ไม่บังคับ) + reverse DNS (timeout 1 วินาที, cache) | ทดสอบแล้ว (GeoIP ยังไม่เคยทดสอบกับไฟล์จริง) |
| `backend/app/db.py` | connection pool แบบ lazy, `scoped_cursor()`, `insert_events()` | **ทดสอบแล้ว** |
| `backend/app/policy.py` | tenant resolution + field-level RBAC | **ทดสอบแล้ว** |
| `backend/app/config.py` | อ่าน env (`DATABASE_URL` บังคับต้องมี) | ใช้ได้ |
| `backend/app/worker.py` | retention วันละครั้ง (ส่วน alert เป็น TODO) | เขียนแล้ว ยังไม่ได้รัน worker จริง |
| `backend/app/main.py` | มีแค่ `GET /api/health` | stub |
| `backend/app/auth.py`, `routes.py` | ว่าง (1 บรรทัด TODO) | **ยังไม่ทำ** |
| `frontend/` | Vite + React ขั้นต่ำ (หน้าเปล่า) | stub |
| `samples/` | ไฟล์ตัวอย่างครบ 7 แหล่ง, `send_syslog.sh`, `post_logs.py` · `simulator.py` เป็น stub | บางส่วน |
| `scripts/get_geoip.sh` | ดาวน์โหลด DB-IP City Lite | ยังไม่เคยดาวน์โหลดจริง |
| `terraform/` | EC2 + Elastic IP + security group + `.env` สุ่มรหัสผ่าน | ยังไม่เคย validate/apply |
| `.github/workflows/` | `ci.yml` (test+build), `deploy.yml` (กดรันเอง) | ยังไม่เคยรันบน GitHub |
| `tests/` | 5 ไฟล์ | ดูหัวข้อ 8 |
| `docs/` | architecture, setup_appliance, setup_saas เขียนแล้ว · Postman ยังไม่มี | บางส่วน |

## 5. วิธีรันและทดสอบ

### ขั้นแรกที่ควรทำทันที: smoke test Compose (ยังไม่เคยมีใครรัน)
```bash
cp .env.example .env        # แก้รหัสผ่าน change_me_* (ใช้ตัวอักษร/ตัวเลขเท่านั้น เพราะอยู่ใน URL)
make up
docker compose ps           # ทุก service ต้องขึ้น
curl -k https://localhost/api/health
bash samples/send_syslog.sh # แล้วดู docker compose logs ingest ว่าขึ้น "stored N syslog events"
docker compose exec postgres psql -U $POSTGRES_USER -d logdb -c "select source, action, src_ip, extra from events"
```
ถ้าไม่ผ่านให้แก้ก่อนสร้างฟีเจอร์ใหม่ เพราะทุกอย่างต่อจากนี้พึ่งพา compose

### รัน test กับ Postgres ตัวจริง (ปิดช่องว่างที่เคยทดสอบด้วย Postgres บน Ubuntu)
```bash
docker run -d --name pgtest -p 5432:5432 \
  -e POSTGRES_PASSWORD=testpw -e POSTGRES_DB=logdb -e APP_DB_PASSWORD=apppw \
  -v "$PWD/db:/docker-entrypoint-initdb.d:ro" postgres:16-alpine
export DATABASE_URL=postgresql://log_app:apppw@localhost:5432/logdb
export DATABASE_ADMIN_URL=postgresql://postgres:testpw@localhost:5432/logdb
pip install -r backend/requirements.txt && pytest -q tests
```
ผลที่เคยได้: **16 ผ่าน 1 skip** เมื่อมี DB · **10 ผ่าน 7 skip** เมื่อไม่ตั้ง env ของ DB
ถ้าอยากพิสูจน์ว่า test แยก tenant ใช้ได้จริง ให้ปิด RLS (`ALTER TABLE events NO FORCE ROW LEVEL SECURITY; ALTER TABLE events DISABLE ROW LEVEL SECURITY;`) แล้วรันใหม่ test เรื่องการแยก tenant ควร **ล้ม** (ยังไม่เคยทำ negative control นี้)

หมายเหตุ: `db/*.sql` และ `db/*.sh` รันเฉพาะ **ครั้งแรกที่ volume ว่าง** แก้ schema แล้วต้อง `make reset` (ลบข้อมูลทั้งหมด)

## 6. Schema และการ map ฟิลด์

ฟิลด์ในโจทย์ → คอลัมน์: `@timestamp`→`ts` · `user`→`user_name` · `_tags`→`tags` · `cloud.*`→`cloud` (JSONB: account_id, region, service) · ฟิลด์ที่ schema ไม่มี (เช่น `sha256`, `workload`, `logon_type`, `event_id`, ผล enrichment) → `extra` (JSONB) · ข้อความต้นฉบับ → `raw` (เก็บเสมอ ถ้าเป็น dict ให้ `json.dumps`)
Primary key ของ `events` คือ `(id, tenant, ts)` (partition ต้องการ)

### แนวทาง map ต่อแหล่ง (ที่เสนอไว้ ยังไม่ได้เขียนโค้ด ยกเว้น syslog)
| source | การแปลง |
|---|---|
| firewall/network (syslog) | **ทำแล้ว:** `<PRI>`→severity (0-10), `key=value`→ฟิลด์ (`src`→`src_ip`, `spt`→`src_port`, `proto`→`protocol`, `policy`→`rule_name`) |
| api | `ip`→`src_ip`, `reason`→`extra.reason`, `app_login_failed` → `action=login`, `event_subtype=failed` |
| crowdstrike | `sha256`→`extra.sha256`, `action=quarantine` ไม่อยู่ใน enum ของโจทย์ → แนะนำ `action=alert`, `event_subtype=quarantine` |
| aws | `cloud`→`cloud`, `raw` เป็น dict→JSON string, ได้ `action` จากชื่อ event (`Create*`→create, `Delete*`→delete, `ConsoleLogin`→login) |
| m365 | `UserLoggedIn`→`action=login`, `status` Success/Failed→`event_subtype`, `ip`→`src_ip`, `workload`→`extra` |
| ad | `event_id` 4625→`action=login`+`event_subtype=failed`, 4624→success, `ip`→`src_ip`, `logon_type`/`event_id`→`extra` |

**ข้อตกลงที่ alert ต้องพึ่งพา:** "login ล้มเหลว" = `action='login' AND event_subtype='failed' AND src_ip IS NOT NULL` ทุก normalizer ต้องตั้งสองฟิลด์นี้ให้ตรงกัน ไม่เช่นนั้น alert จะไม่ยิง

## 7. งานที่เหลือ เรียงตามลำดับที่แนะนำ

| # | งาน | หมวดคะแนน |
|---|---|---|
| 0 | smoke test Compose (หัวข้อ 5) และแก้ปัญหาที่เจอ | Deployment |
| 1 | normalizer ที่เหลือ 5 แหล่ง + dispatcher + เติมช่องว่างของ syslog (หัวข้อ 8 ข้อ 4) | Ingestion, Normalization |
| 2 | auth: `POST /api/auth/login`, JWT `{sub, role, tenant}`, seed users จาก `ADMIN_PASSWORD`/`VIEWER_PASSWORD` (bcrypt) ตอน startup, dependency ดึง claims | Security |
| 3 | `POST /api/ingest` (event เดียว/array/NDJSON) + `POST /api/ingest/file?source=` เรียก `enrich()` และตอบจำนวนที่รับ/ปฏิเสธ | Ingestion |
| 4 | `GET /api/search`, `/api/stats/top`, `/api/stats/timeline` ใช้ `scoped_cursor` + `resolve_tenant` + `filter_fields` | Storage & Query, Security |
| 5 | alert engine ใน `worker.py` + หน้า alert + webhook (ใช้ webhook.site ตอน demo) | Alerting |
| 6 | frontend 4 หน้า: Login, Dashboard (Top IP/User/Event type, timeline, filter เวลา/tenant/source), Search, Alerts | Dashboard |
| 7 | `samples/simulator.py` (สุ่ม event ทั้ง 7 แหล่ง, โหมดกระตุ้น alert, ใช้ IP สาธารณะจริงเพื่อให้เห็น enrichment) + แก้ `post_logs.py` ให้ใช้เวลาปัจจุบัน | Ingestion |
| 8 | test เพิ่ม: normalizer ต่อแหล่ง, alert rule, tenant isolation ระดับ API | Tests |
| 9 | Postman collection, เอกสารให้ตรงกับของจริง, ลอง Terraform และ CI บน GitHub, อัดวิดีโอ demo | Docs, Deployment |

### API ที่วางแผนไว้ (ยังไม่มีในโค้ด)
| Endpoint | สิทธิ์ | หมายเหตุ |
|---|---|---|
| `POST /api/auth/login` | public | คืน JWT |
| `POST /api/ingest` | ดูหัวข้อ 9 | ต้องเช็กว่า tenant ใน payload ได้รับอนุญาต |
| `POST /api/ingest/file?source=` | admin | อัปโหลดไฟล์ JSON/NDJSON |
| `GET /api/search` | viewer/admin | filter: เวลา, source, event_type, ข้อความ, pagination |
| `GET /api/stats/top`, `/stats/timeline` | viewer/admin | Top IP/User/Event type |
| `GET /api/alerts`, `/alert-rules` | viewer/admin | |
| `POST /api/tenants` | admin | เรียก `provision_tenant()` |

## 8. ปัญหาที่รู้อยู่แล้วและข้อควรระวัง

1. **ชื่อ partition ชนกัน (ระดับกลาง)** tenant `a_20991231` ชนกับ partition รายวันของ tenant `a` วันที่ 2099-12-31 เพราะ `CREATE TABLE IF NOT EXISTS` ข้ามเงียบๆ → `provision_tenant` ดูสำเร็จแต่ tenant นั้น insert ไม่ได้ (ไม่รั่วข้อมูลข้าม tenant แต่ทำให้เข้าใจผิด) ชื่อในโจทย์อย่าง `demoA` ไม่โดน **ทดสอบยืนยันแล้ว** วิธีแก้ที่เสนอ: ใช้ prefix ต่างกัน (`events_t_<tenant>` ระดับ tenant, `events_d_<tenant>_<YYYYMMDD>` ระดับวัน), ให้ `ensure_tenant` raise error ถ้ามีตารางชื่อนั้นอยู่แล้วแต่ไม่ใช่ partition ของ tenant, ให้ `drop_old_partitions` ใช้ `relispartition`/`relkind` แทนการเดาจากตัวเลขท้ายชื่อ และเพิ่ม test เคสนี้
2. **listener ทิ้งทั้ง batch เมื่อ insert ล้ม (กลาง)** เช่นแถวเดียวไม่มี partition หรือ tenant ไม่ถูกต้อง ตอนนี้แค่ print แล้วทิ้ง ควรแยกแถวเสียและนับ rejected
3. **timestamp นอกหน้าต่าง partition (กลาง)** partition มีเฉพาะวันนี้ −7 ถึง +2 วัน (สร้างตอน init และโดย worker ทุกวัน) event ที่เวลาอยู่นอกช่วงจะ insert ล้ม ไฟล์ตัวอย่างในโจทย์ใช้วันที่ปี 2025 ซึ่งจะไม่ผ่าน ต้องตัดสินใจ (หัวข้อ 9)
4. **syslog ยังไม่สมบูรณ์ (กลาง)** `normalize_syslog` ใช้ tenant ค่าเดียวจาก `DEFAULT_TENANT`, ใช้เวลาที่รับแทนเวลาใน log (ไม่มีปีใน syslog และยังไม่ได้ parse), ตามโค้ดปัจจุบันยังไม่ตั้ง `event_type`/`host`/`user` (ทำให้ `event=link-down` ของ router หายไป) และแยก firewall/network ด้วยการเดาว่ามี `src` หรือไม่
5. **ขอบเขตของ RLS (ต่ำ)** ป้องกันบั๊กใน API ไม่ได้ป้องกัน app server ที่ถูกเจาะ เพราะ code path ของ insert ตั้ง `app.is_admin='on'` เอง และ partition-per-tenant เหมาะกับ tenant หลักสิบ (ไม่ใช่หลักพัน)
6. **ของที่ยังไม่เคยรันจริง:** Compose, Terraform, GitHub Actions, `make geoip` (URL ของ DB-IP อิงจากรูปแบบที่จำได้ ถ้าโหลดไม่ได้ให้วางไฟล์ `.mmdb` ที่ `data/geoip/city.mmdb` เอง), พฤติกรรม `docker-entrypoint-initdb.d` กับ `02_app_role.sh`
7. **enrichment ข้าม IP ตัวอย่างของโจทย์** (`203.0.113.x`, `198.51.100.x` เป็นช่วงสำหรับเอกสาร) ตอน demo ต้องใช้ IP สาธารณะจริง ถ้าใช้ GeoIP DB-IP ต้องใส่เครดิต "IP Geolocation by DB-IP" (CC BY 4.0)
8. **frontend:** nginx ใช้ค่า default ไม่มี fallback ไป `index.html` ถ้าใช้ client-side routing ต้องเพิ่ม config และ `npm install` ไม่มี lockfile
9. **ความลับ:** `make up` สร้าง `.env` จาก `.env.example` ที่เป็นรหัสผ่านตัวอย่าง ต้องเปลี่ยนก่อนขึ้น SaaS และ `JWT_SECRET` ยังไม่ถูกบังคับให้ตั้ง (ต้องเพิ่มเช็กตอนเขียน auth) รหัสผ่านใน Terraform อยู่ใน state และ user-data
10. **`insert_events` ข้ามแถวที่ไม่มี tenant เงียบๆ** และคืนแค่จำนวนที่ insert API ที่เขียนต่อควรรายงานจำนวนที่ปฏิเสธให้ผู้เรียก
11. **สภาพแวดล้อมทดสอบต่างจาก Compose** ผมทดสอบกับ Postgres 16 จาก Ubuntu ไม่ใช่ `postgres:16-alpine` และไม่มี Docker ในเครื่องที่ใช้ทดสอบ

## 9. ประเด็นที่ยังต้องตัดสินใจ

| ประเด็น | ตัวเลือก | ข้อเสนอ |
|---|---|---|
| ใครเรียก `POST /api/ingest` ได้ | JWT admin อย่างเดียว / API key ต่อ tenant | เริ่มด้วย JWT admin ถ้ามีเวลาค่อยเพิ่ม API key ต่อ tenant |
| tenant ของ syslog | map ตาม IP ผู้ส่ง / หนึ่งพอร์ตต่อ tenant / ค่า default | map ตาม IP ผู้ส่ง (เห็นการแยก tenant ใน demo ชัดสุด) |
| timestamp นอกช่วง partition | เขียนทับเป็นเวลาปัจจุบัน / ปฏิเสธพร้อมแจ้ง | ไฟล์ตัวอย่างใช้เขียนทับตอนส่ง ส่วน API จริงควรปฏิเสธและรายงาน |
| จะแก้ปัญหาชื่อ partition ชนหรือไม่ | แก้ / จำกัดชื่อ tenant | แก้ด้วย prefix แยก (เปลี่ยนน้อย) |
| จะเก็บ partition-per-tenant ไว้ไหม | เก็บ / กลับไป partition รายวันอย่างเดียว | เก็บไว้ (ได้โบนัส multi-tenancy) แต่ต้องอธิบายข้อจำกัดเรื่องจำนวน tenant ได้ |

## 10. Acceptance checklist ของโจทย์

| ข้อ | สถานะ |
|---|---|
| เริ่ม Appliance ด้วยไม่กี่คำสั่ง | เขียนไว้ ยังไม่ได้ทดสอบ |
| ส่ง syslog แล้วเห็นใน UI ภายใน 1 นาที | ถึง DB แล้ว ยังไม่มี UI |
| `POST /ingest` แล้วค้นเจอ | ยังไม่ทำ |
| อัปโหลดไฟล์ AWS/M365/AD แล้ว normalize | ยังไม่ทำ |
| Top N, Timeline, filter tenant/source/time | ยังไม่ทำ |
| Alert แล้วเห็นแจ้งเตือน | ยังไม่ทำ |
| Viewer เห็นเฉพาะ tenant ตัวเอง | ชั้น DB และ policy พร้อม ยังไม่มี login |
| เข้า SaaS ผ่าน HTTPS | Caddy + Terraform เขียนไว้ ยังไม่ได้ deploy |

## 11. ข้อแนะนำสำหรับผู้รับช่วง

- งานที่ผ่านมาเน้นฐานราก (DB, tenant isolation, Nice-to-have) หมวดที่คะแนนสูงอย่าง Ingestion (20), Dashboard (10), Alerting (10) ยังเป็นศูนย์ ควรเร่งข้อ 0-6 ในหัวข้อ 7 ก่อนแตะโบนัสเพิ่ม
- โค้ดฝั่ง DB และ tenant เขียนเสร็จแล้ว ใน endpoint ใหม่ทุกตัวให้ใช้ `scoped_cursor()` + `resolve_tenant()` + `filter_fields()` เสมอ อย่าอ่าน tenant จาก parameter ของ client สำหรับ viewer
- เมื่อแก้ schema ให้รัน `pytest` กับ Postgres จริงทุกครั้ง บั๊กของ schema รอบก่อนถูกพบจากการรัน SQL จริง ไม่ใช่จากการอ่านโค้ด
- ความเข้าใจผิดที่เคยเกิดและแก้แล้ว: ตัวเลขที่ตรวจ partition ได้ 140 เกิดจาก query ตรวจที่นับ index ลูกติดมาด้วย (120 index + 20 ตาราง) ไม่ใช่ schema ผิด
