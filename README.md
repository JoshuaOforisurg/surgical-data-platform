# Theatre Data Platform
Description: 
This platform is a unified, modular data platform for operating theatre operations, intelligence, and AI training.

## Vision
From my personal experience working in the operating theatre, the "hidden" cost of care is often found in disjointed systems 
and manual, inconsistent documentation. 
This platform is designed from a clinical perspective to create a single, unified architecture that supports:

- Real-time theatre operations  
- Analytics and intelligence  
- AI and robotics training data  

All modules follow the same engineering lifecycle and share a common core.

---

## Platform Architecture

### Core Layer
Shared functionality used by all modules:
- Ingestion  
- Validation  
- Logging  
- Scheduling  
- Storage  
- Utilities  

### Module Layer (Categorisation of pipelines)

#### Operational Modules
Description: These are core pipelines which support day-to-day theatre operations:
- Surgeon Preference  
- Loan Kit  
- Instrument tracking
- Anaesthetic  
- Stock Management  
- Case Scheduling  

Intelligence Modules: 
Description: These pipelines support efficiency, providing intelligence for analytics-ready pipelines for theatre insights:
- Brief & Debrief  
- Turnaround Time  
- Theatre Utilisation  
- Staffing Efficiency  

#### AI & Training Modules: 
Description: Pipelines here feed into ML models for surgical training and robotics: 
- Surgical Video  
- Robotics  
- Instrument Tracking  

### Shared Layer
- JSON schemas  
- Config files  
- Common models  

---

## Repository Structure

theatre-data-platform/
│
├── README.md
├── docs/
│   ├── overview.md
│   ├── architecture.md
│   ├── modules.md
│   ├── data_models/
│   └── roadmap.md
│
├── platform/
│   ├── core/
│   ├── modules/
│   │   ├── operational/
│   │   ├── intelligence/
│   │   └── ai_training/
│   └── shared/
│
└── tests/

---

## Platform Lifecycle
All modules follow the same lifecycle:

1. Ingest  
2. Validate  
3. Transform  
4. Log  
5. Load  
6. Schedule  
7. Document  

---

## Roadmap
- Add synthetic data generator and data from public data sources
- Transform data to ensure schema validation
- Add FHIR/HL7 integration 
- Add orchestration (Airflow)  
- Add dashboards  
- Add ML models  
- Add CI/CD  


---

## Author
GitHub: JoshuaOforisurg
