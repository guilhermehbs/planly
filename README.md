# Planly

Planly e um sistema web para planejamento financeiro de clientes, com perfis de administrador, planejador e cliente.

## Recursos

- Login com perfis de administrador, planejador e cliente.
- Administrador pode alterar usuarios para planejador e excluir usuarios.
- Planejador gerencia clientes, categorias globais, percentuais por categoria, reunioes, metas, gastos, ganhos e dividas.
- Cliente registra ganhos e gastos, acompanha metas por categoria, dividas e dashboard mensal.
- Filtro mensal por mes e ano para gastos, ganhos, dividas e dashboards.
- Compras parceladas sao distribuidas automaticamente entre os meses das parcelas.
- Dashboards com graficos de gastos, ganhos, dividas e uso de limite.

## Configuracao

Copie `.env.example` para `.env` e preencha os valores do seu ambiente. Nunca versione o arquivo `.env`.

Variaveis principais:

```text
PLANLY_HOST=127.0.0.1
PLANLY_PORT=8000
PLANLY_DB_PATH=./planejamento_financeiro.db
DATABASE_URL=
PLANLY_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
PLANLY_SESSION_TTL_HOURS=12
PLANLY_SESSION_COOKIE_SAMESITE=Lax
PLANLY_COOKIE_SECURE=false
PLANLY_PUBLIC_ERROR_DETAILS=false
PLANLY_ADMIN_EMAIL=
PLANLY_ADMIN_PASSWORD=
VITE_API_URL=http://127.0.0.1:8000/api
```

O administrador inicial so e criado quando `PLANLY_ADMIN_EMAIL` e `PLANLY_ADMIN_PASSWORD` estiverem definidos e ainda nao existir outro admin no banco.

## Como executar

Em um terminal, suba a API:

```powershell
python -m backend.main
```

Em outro terminal, instale e rode o frontend:

```powershell
cd frontend
npm install
npm run dev
```

Acesse a URL exibida pelo Vite, normalmente `http://127.0.0.1:5173`.

## Seguranca

- Nao ha senhas ou e-mails reais versionados no codigo.
- Sessao de usuario usa cookie `HttpOnly`.
- Alteracoes de dados exigem token CSRF por sessao.
- CORS e limitado por `PLANLY_ALLOWED_ORIGINS`.
- O banco SQLite local, `.env`, builds, caches e exports privados ficam fora do Git pelo `.gitignore`.
- Em producao, use HTTPS e defina `PLANLY_COOKIE_SECURE=true`.
- Mantenha `PLANLY_PUBLIC_ERROR_DETAILS=false` em producao para nao expor detalhes internos.
- O frontend nao armazena token de sessao em `localStorage` ou `sessionStorage`.
- Usuarios podem ver no DevTools qualquer dado que o backend enviar para o perfil deles. Por isso, a regra de seguranca e: o backend nunca deve retornar dados fora da permissao do usuario autenticado.

## Deploy em producao

Use `.env.production.example` como base. Em producao, o backend bloqueia a inicializacao se detectar configuracoes inseguras, como CORS com localhost, cookie sem `Secure`, detalhes publicos de erro ou senha inicial fraca.

Para frontend e backend em dominios diferentes:

```text
PLANLY_SESSION_COOKIE_SAMESITE=None
PLANLY_COOKIE_SECURE=true
PLANLY_ALLOWED_ORIGINS=https://seu-front.vercel.app
```

SQLite local nao e recomendado para producao com deploy em nuvem. Prefira Postgres gerenciado. Se insistir em SQLite, defina `PLANLY_ALLOW_SQLITE_IN_PRODUCTION=true` conscientemente e garanta disco persistente, backup, criptografia e controle de acesso no servidor.

Para usar Supabase/Postgres, defina `DATABASE_URL` no backend. Quando `DATABASE_URL` existe, o Planly ignora o SQLite local e usa Postgres. Para copiar os dados atuais do SQLite para o Postgres:

```powershell
$env:DATABASE_URL="postgresql://..."
python scripts/migrate_sqlite_to_postgres.py
```

No Render, deixe a plataforma definir `PORT` automaticamente. Nao defina `PLANLY_PORT` no painel do Render, a menos que esteja rodando fora da plataforma.

## LGPD

Este sistema armazena dados pessoais e financeiros de clientes. Ao operar o Planly:

- Colete apenas dados necessarios para o planejamento financeiro.
- Restrinja acesso por perfil de usuario e revise periodicamente quem e planejador/admin.
- Nao versione bancos, exports, logs ou arquivos com dados pessoais.
- Remova usuarios/clientes quando solicitado pelo titular dos dados, respeitando obrigacoes legais aplicaveis.
- Informe os titulares sobre finalidade, acesso, correcao e exclusao dos dados.
- Use backups protegidos e com politica de retencao definida.

## Estrutura

```text
backend/              # API HTTP, autenticacao, permissoes e dashboards
core/                 # Configuracoes e formatadores compartilhados
data/                 # SQLite local ou Supabase/Postgres e operacoes de persistencia
frontend/             # Frontend React
.env.example          # Modelo de configuracao sem segredos reais
.gitignore            # Exclusoes para GitHub
```
