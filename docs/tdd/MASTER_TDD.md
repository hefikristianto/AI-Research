# AI-TDSS MASTER TDD

---

## Document Information

| Item | Description |
|------|-------------|
| Project | AI-TDSS |
| Document | Technical Development Document |
| Version | 2.0 |
| Status | Active |
| Author | Hefi Kristianto |
| Last Updated | 01-07-2026 |

---

# Preface

MASTER TDD merupakan dokumen utama teknis pengembangan AI-TDSS.

Dokumen ini menjadi acuan implementasi teknis untuk backend, frontend, database, AI pipeline, dataset, training model, evaluasi, deployment, dan pengembangan lanjutan.

TDD tidak menggantikan SDD.  
SDD menjelaskan desain sistem, sedangkan TDD menjelaskan cara implementasi teknis sistem.

---

# Development Status

| Sprint | Module | Status |
|--------|--------|--------|
| Sprint 1 | Foundation | Completed |
| Sprint 2 | Dataset Engineering | In Progress |
| Sprint 3 | Annotation System | Planned |
| Sprint 4 | Dataset Validation | Planned |
| Sprint 5 | YOLO Benchmark | Planned |
| Sprint 6 | Zone Filtering Engine | Planned |
| Sprint 7 | Zone Scoring Engine | Planned |
| Sprint 8 | CNN Ensemble Validator | Planned |
| Sprint 9 | Price Conversion Engine | Planned |
| Sprint 10 | Analysis Engine | Planned |
| Sprint 11 | LLM Decision Engine | Planned |
| Sprint 12 | Analysis Dashboard | Planned |
| Sprint 13 | Trading Journal | Planned |
| Sprint 14 | Performance Evaluation | Planned |
| Sprint 15 | Incremental Learning | Planned |
| Sprint 16 | Explainable AI | Planned |
| Sprint 17 | Research Mode | Planned |
| Sprint 18 | Deployment | Planned |
| Sprint 19 | Thesis Completion | Planned |
| Sprint 20 | Final Release | Planned |

---

# Chapter List

| Chapter | File |
|---------|------|
| Chapter 1 | chapters/CH01_Project_Setup.md |
| Chapter 2 | chapters/CH02_Backend.md |
| Chapter 3 | chapters/CH03_Frontend.md |
| Chapter 4 | chapters/CH04_Dataset_Engineering.md |
| Chapter 5 | chapters/CH05_Annotation_System.md |
| Chapter 6 | chapters/CH06_Dataset_Validation.md |
| Chapter 7 | chapters/CH07_YOLO_Benchmark.md |
| Chapter 8 | chapters/CH08_Zone_Filtering.md |
| Chapter 9 | chapters/CH09_Zone_Scoring.md |
| Chapter 10 | chapters/CH10_CNN_Validation.md |
| Chapter 11 | chapters/CH11_Price_Conversion.md |
| Chapter 12 | chapters/CH12_Analysis_Engine.md |
| Chapter 13 | chapters/CH13_LLM_Decision_Engine.md |
| Chapter 14 | chapters/CH14_Analysis_Dashboard.md |
| Chapter 15 | chapters/CH15_Trading_Journal.md |
| Chapter 16 | chapters/CH16_Performance_Evaluation.md |
| Chapter 17 | chapters/CH17_Incremental_Learning.md |
| Chapter 18 | chapters/CH18_Explainable_AI.md |
| Chapter 19 | chapters/CH19_Deployment.md |
| Chapter 20 | chapters/CH20_Final_Release.md |

---

# Technical Stack

## Backend

- Python
- FastAPI
- Uvicorn
- Supabase Python Client
- PostgreSQL
- Supabase Auth
- Supabase Storage

## Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- Axios
- js-cookie
- react-dropzone

## AI / Machine Learning

- YOLOv8
- YOLO11
- YOLO26
- VGG11
- VGG16
- ResNet
- GoogLeNet
- PyTorch
- Ultralytics
- OpenCV

## Database

- Supabase PostgreSQL
- Row Level Security
- Auth-linked user data
- Screenshot metadata
- Analysis results
- Trading journal
- Feedback learning data

## Deployment

- Frontend: Vercel
- Backend: Railway / VPS
- Database: Supabase
- Storage: Supabase Storage

---

# Development Workflow

Setiap pengembangan fitur mengikuti alur berikut:

```text
Requirement
    ↓
SDD Update
    ↓
TDD Update
    ↓
Implementation
    ↓
Testing
    ↓
Decision Log Update
    ↓
Changelog Update
    ↓
Git Commit
    ↓
Git Push

# Git Workflow

Setiap perubahan besar wajib disimpan ke GitHub.

git status
git add .
git commit -m "type: description"
git push

Contoh:

git commit -m "docs: update TDD roadmap"
git commit -m "feat: add analysis endpoint"
git commit -m "fix: resolve upload metadata issue"

---

# Backend Development Command

Aktifkan virtual environment:

cd C:\Users\ASUS\Documents\Project\AI-TDSS\backend
.\.venv\Scripts\Activate.ps1

Jalankan backend:

uvicorn main:app --reload


Cek Python:


python --version
where python

Keluar dari virtual environment:

deactivate


---

# Frontend Development Command

Masuk frontend:

cd C:\Users\ASUS\Documents\Project\AI-TDSS\frontend

Jalankan frontend:

npm run dev

---

# Documentation Rules

1. MASTER_TDD hanya berfungsi sebagai index utama.
2. Detail implementasi berada pada masing-masing chapter.
3. Setiap chapter wajib menjelaskan:
   - Objective
   - Technical Scope
   - Folder Structure
   - Files
   - Implementation Steps
   - Testing
   - Expected Output
4. Perubahan implementasi wajib memperbarui TDD.
5. Perubahan arsitektur wajib memperbarui SDD.
6. Perubahan keputusan wajib dicatat pada Decision Log.
7. Perubahan versi wajib dicatat pada Changelog.
8. Seluruh sprint wajib mengikuti Sprint Backlog.

---

# Current Development Focus

Sprint saat ini:

**Sprint 2 - Dataset Engineering**

Prioritas:

- Menentukan struktur dataset
- Menentukan metadata
- Menentukan folder dataset
- Memisahkan pair
- Memisahkan timeframe
- Memisahkan market session
- Menentukan kategori news
- Menyusun standar dataset untuk proses labeling

---

# Notes

Sprint 1 telah selesai dan menghasilkan:

- FastAPI Backend
- Next.js Frontend
- Authentication
- Dashboard
- Upload UI
- Upload API
- Supabase Storage
- Screenshot Metadata
- GitHub Repository
- Documentation Foundation

Tahap berikutnya adalah membangun Dataset Engineering sebagai fondasi sebelum proses Annotation, Benchmark YOLOv8, YOLO11, YOLO26, serta pembangunan Analysis Engine.

