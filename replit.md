# CiviPro Ultimate - SaaS Engenharia Civil

## Overview

CiviPro Ultimate é uma plataforma SaaS completa para engenheiros civis gerenciarem projetos de construção, incluindo clientes, fornecedores, materiais, mão de obra, equipamentos e orçamentos detalhados. O sistema oferece rastreamento de projetos, biblioteca completa de recursos, cálculo automático de orçamentos (materiais + mão de obra + equipamentos), exportação de PDF profissional, dashboard avançado com gráficos e alertas, e simulador de cenários.

Esta versão **CiviPro Ultimate** inclui todas as funcionalidades do MVP original mais recursos avançados para gestão completa de projetos de engenharia civil, com foco no mercado brasileiro (idioma português, formatação de moeda brasileira).

**Status:** ✅ **COMPLETO** - Sistema totalmente funcional com todas as funcionalidades principais e avançadas implementadas (Outubro 2025)

**Fase Atual:** Fase 3 - Sistema de Assinatura e Monetização com Mercado Pago ✅

**Créditos:** Todos os componentes do sistema incluem atribuição a **João Layon - Desenvolvedor Full Stack** conforme requisitos.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture

**Technology Stack:**
- **HTML5 Templates** using Jinja2 templating engine
- **TailwindCSS** via CDN for responsive styling
- **Chart.js** for data visualization capabilities
- **Vanilla JavaScript** for theme toggling and mobile menu interactions

**Design Decisions:**
- **Responsive-first approach**: Mobile-friendly design with collapsible sidebar for smaller screens
- **Dark/Light theme support**: User preference stored in localStorage with system preference fallback
- **Component-based templates**: Base template inheritance pattern for consistent UI across pages
- **Real-time theme switching**: Client-side JavaScript handles theme toggle without page reload

**UI Components:**
- Sidebar navigation (desktop) with responsive mobile menu
- Dashboard with metric cards showing project statistics
- CRUD interfaces for projects and materials
- Form-based data entry with validation
- Tabular data display with inline actions

### Backend Architecture

**Framework:** Flask (Python micro-framework)

**Rationale:** Flask provides lightweight, flexible web application structure suitable for MVP development with minimal overhead. No heavy ORM dependencies allows for direct SQL control and simpler deployment.

**Authentication & Authorization:**
- Session-based authentication using Flask sessions
- Password hashing with werkzeug.security (generate_password_hash, check_password_hash)
- User isolation: Database queries filtered by session user_id
- No role-based access control in MVP (single user type)

**Application Structure:**
- **Monolithic app.py**: All routes and business logic in single file for MVP simplicity
- **Template-driven rendering**: Server-side rendering with Jinja2
- **Session management**: Flask secret key for session security (environment variable configurable)

**Core Features (MVP + Fase 2):**

**MVP Base:**
1. **User Management**: Registro, login, logout com hash de senha
2. **Project Management**: Operações CRUD para projetos com cliente, área, nível de acabamento e prazo
3. **Material Library**: Banco de dados centralizado de materiais com preço por unidade

**Fase 2 - Recursos Avançados:**
4. **Client Management**: CRUD completo para clientes com edição inline (nome, email, telefone, CPF/CNPJ)
5. **Supplier Management**: CRUD para fornecedores com dados de contato completos
6. **Labor Management**: Biblioteca de categorias de mão de obra (pedreiro, eletricista, etc.) com valores hora/dia
7. **Equipment Management**: Catálogo de equipamentos com valores de aluguel/compra
8. **Advanced Budget System**: Cálculo automático separado por tipo (materiais + mão de obra + equipamentos)
9. **Enhanced PDF Export**: Documentos profissionais com breakdown detalhado por categoria e subtotais
10. **Advanced Dashboard**: 
    - 6 cards de métricas (projetos, clientes, fornecedores, materiais, mão de obra, equipamentos)
    - Gráfico de pizza: distribuição de custos por tipo

**Fase 3 - Sistema de Assinatura:**
11. **Mercado Pago Integration**: Sistema completo de assinatura recorrente
    - Teste grátis de 7 dias automático para novos usuários
    - Três planos de assinatura (Básico R$97, Profissional R$197, Enterprise R$397)
    - Processamento de pagamentos via Mercado Pago (cartão, PIX, boleto)
    - Webhook para sincronização automática de status de assinatura
12. **Subscription Management**: 
    - Página de planos e preços com comparação de recursos
    - Dashboard de gerenciamento de assinatura do usuário
    - Cancelamento de assinatura com um clique
    - Banner visual mostrando dias restantes do trial
13. **Access Control**: 
    - Middleware para verificar status de assinatura ativa
    - Bloqueio automático de acesso quando trial/assinatura expira
    - Redirecionamento para página de planos quando necessário
14. **Budget Scenario Simulator**: Ferramenta interativa para simular diferentes configurações de orçamento

**Business Logic:**
- Orçamento calculado com base em área do projeto, tipo (residencial/comercial/industrial) e nível de acabamento
- Multiplicadores automáticos por tipo de obra (residencial: 1.0x, comercial: 1.3x, industrial: 1.5x)
- Multiplicadores por acabamento (simples: 1.0x, médio: 1.5x, alto: 2.0x)
- Custos separados por categoria: materiais, mão de obra, equipamentos
- Isolamento de dados por usuário garante multi-tenancy seguro
- Relacionamentos entre projetos e clientes via foreign key client_id

### Data Storage

**Database:** SQLite3 (file-based, no external server required)

**Rationale:** 
- **Pros**: Zero configuration, file-based portability, sufficient for MVP scale, built into Python
- **Cons**: Limited concurrency, not suitable for high-traffic production (noted for future migration)
- **Migration path**: Structure supports future PostgreSQL migration with minimal query changes

**Schema Design:**

**users table:**
- id (PRIMARY KEY, AUTOINCREMENT)
- name (TEXT, NOT NULL)
- email (TEXT, UNIQUE, NOT NULL)
- password_hash (TEXT, NOT NULL)
- created_at (TEXT - ISO format timestamp)
- trial_start_date (TEXT - ISO format timestamp do início do trial)
- trial_end_date (TEXT - ISO format timestamp do fim do trial)
- subscription_status (TEXT - 'trial', 'active', 'cancelled', 'trial_expired')
- subscription_id (TEXT - ID da assinatura no Mercado Pago)
- plan_id (TEXT - 'basic', 'professional', 'enterprise')

**projects table:**
- id (PRIMARY KEY, AUTOINCREMENT)
- user_id (INTEGER, foreign key to users)
- client_id (INTEGER, foreign key to clients - optional)
- name (TEXT)
- client (TEXT - legacy field for ad-hoc client names)
- area (REAL - square meters)
- project_type (TEXT - 'residencial', 'comercial', 'industrial')
- finish_level (TEXT - 'simples', 'medio', 'alto')
- status (TEXT - 'em_andamento', 'pausado', 'concluido')
- deadline (TEXT - date format)
- notes (TEXT)
- real_cost (REAL - custo real executado)
- created_at (TEXT - timestamp)

**clients table:**
- id (PRIMARY KEY, AUTOINCREMENT)
- user_id (INTEGER, foreign key to users)
- name (TEXT, NOT NULL)
- email (TEXT)
- phone (TEXT)
- cpf_cnpj (TEXT)
- address (TEXT)
- created_at (TEXT - timestamp)

**suppliers table:**
- id (PRIMARY KEY, AUTOINCREMENT)
- user_id (INTEGER, foreign key to users)
- name (TEXT, NOT NULL)
- email (TEXT)
- phone (TEXT)
- cnpj (TEXT)
- address (TEXT)
- product_category (TEXT - categoria de produtos fornecidos)
- created_at (TEXT - timestamp)

**materials table:**
- id (PRIMARY KEY, AUTOINCREMENT)
- user_id (INTEGER, allows user-specific material libraries)
- name (TEXT)
- unit (TEXT - e.g., "m³", "sacos", "un")
- price (REAL - Brazilian Real currency)

**labor table:**
- id (PRIMARY KEY, AUTOINCREMENT)
- user_id (INTEGER)
- category (TEXT - e.g., "Pedreiro", "Eletricista", "Encanador")
- description (TEXT)
- hourly_rate (REAL - valor por hora)
- daily_rate (REAL - valor por dia)

**equipment table:**
- id (PRIMARY KEY, AUTOINCREMENT)
- user_id (INTEGER)
- name (TEXT - nome do equipamento)
- equipment_type (TEXT - 'aluguel' ou 'compra')
- daily_cost (REAL - custo diário de aluguel)
- purchase_cost (REAL - custo de compra)

**budgets table:**
- id (PRIMARY KEY, AUTOINCREMENT)
- project_id (INTEGER, foreign key to projects)
- material (TEXT - nome do item)
- item_type (TEXT - 'material', 'mao_de_obra', 'equipamento')
- quantity (REAL)
- unit (TEXT)
- cost (REAL - custo total = quantidade × preço unitário)

**Data Access Pattern:**
- Direct SQL queries using sqlite3 with parameterized statements
- Row factory set to sqlite3.Row for dictionary-like access
- Connection established per request (get_db_conn helper function)

### External Dependencies

**Python Packages:**
- **Flask**: Web framework (routing, templating, sessions)
- **werkzeug**: Password hashing utilities (bundled with Flask)
- **reportlab**: PDF generation library for budget exports
- **mercadopago**: SDK oficial do Mercado Pago para integração de pagamentos

**CDN Resources:**
- **TailwindCSS** (cdn.tailwindcss.com): CSS framework
- **Chart.js** (cdn.jsdelivr.net): Charting library for future analytics

**Deployment Configuration:**
- **Gunicorn**: WSGI HTTP server for production deployment
- **Render**: Target deployment platform mentioned in documentation
- Environment variable support for SESSION_SECRET configuration

**Browser APIs:**
- localStorage: Theme preference persistence
- matchMedia: System dark mode detection

**File System:**
- SQLite database file (database.db) stored in application directory
- Static assets served from /static directory

**External Services:**
- **Mercado Pago**: Gateway de pagamentos para assinaturas recorrentes (requer MERCADOPAGO_ACCESS_TOKEN)
  - Webhook endpoint: /mercadopago-webhook para sincronização de status
  - Suporte a cartão de crédito, PIX e boleto bancário
  - Trial grátis de 7 dias configurado automaticamente

**Services Not Integrated:**
- No email service (future consideration for notifications)
- No cloud storage (PDFs generated in-memory with BytesIO)
- No third-party authentication (local authentication only)