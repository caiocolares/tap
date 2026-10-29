<div align="center">
  <img src="./img/tap.png" alt="T.A.P. logo" width="600">

  # 🍺 T.A.P. (Text & Audio Parser)

  ![Python](https://img.shields.io/badge/python-3.13-blue.svg)
  ![PyTorch](https://img.shields.io/badge/PyTorch-%23EE4C2C.svg?style=flat&logo=PyTorch&logoColor=white)
  ![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)
  ![Hugging Face](https://img.shields.io/badge/Hugging%20Face-FFD21E.svg?style=flat&logo=huggingface&logoColor=black)
  ![uv](https://img.shields.io/badge/uv-DE5FE9.svg?style=flat&logo=uv&logoColor=white)
  ![MinIO](https://img.shields.io/badge/MinIO-C72E49.svg?style=flat&logo=minio&logoColor=white)
  ![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)

  ### Transcrição tirada na pressão — sem espuma, sem ruído.
</div>

Transcreve um arquivo de áudio (mp3, wav, etc.) para texto usando [faster-whisper](https://github.com/SYSTRAN/faster-whisper) e identifica quem está falando (`pessoa1`, `pessoa2`, ...) usando [pyannote.audio](https://github.com/pyannote/pyannote-audio).

## Índice

- [Escopo](#escopo)
- [Setup](#setup)
- [Autenticação e acesso](#autenticação-e-acesso)
- [Testes](#testes)
- [Uso via CLI](#uso-via-cli)
- [Servidor HTTP](#servidor-http)
  - [Endpoints](#endpoints)
  - [API Assíncrona (Arquivos Grandes)](#api-assíncrona-arquivos-grandes)
- [Performance: CPU vs GPU (Metal)](#performance-cpu-vs-gpu-metal)
- [Docker](#docker)
  - [Docker Compose (API, worker, PostgreSQL e MinIO)](#docker-compose-api-worker-postgresql-e-minio)
  - [OpenShift (Knative Serving)](#openshift-knative-serving)
- [Saída](#saída)
- [Troubleshooting / FAQ](#troubleshooting--faq)
- [Contribuidores](#contribuidores)

## Escopo

O projeto resolve um problema específico: dado um áudio de uma conversa com múltiplos falantes, produzir um texto legível do diálogo, marcando a troca de speaker.

- **Entrada**: um arquivo de áudio (mp3, wav, etc.) — via caminho local (CLI, `transcribe.py`) ou via requisição HTTP com o áudio no corpo (body) da requisição (servidor, `server.py`).
- **Saída**: um arquivo com o diálogo transcrito, uma linha por trecho de fala, prefixado pelo rótulo do speaker (`pessoa1`, `pessoa2`, ...) — em `.txt` (legível) ou `.json` (estruturado).
- **Identificação de speaker é apenas diferencial, não nominal**: o objetivo não é descobrir *quem* é cada pessoa, só sinalizar quando a fala passa de um interlocutor para outro. Por isso os rótulos são genéricos (`pessoa1`, `pessoa2`) e não há reconhecimento de identidade/voz nomeada.
- **Fora do escopo**: reconhecimento de identidade real do falante e tradução do conteúdo.

## Setup

1. Instale o [ffmpeg](https://ffmpeg.org/) no sistema (necessário para decodificar mp3):
   - **macOS** (via Homebrew):
     ```bash
     brew install ffmpeg
     ```
   - **Fedora Linux**:
     ```bash
     sudo dnf install ffmpeg
     ```
   - **Debian / Ubuntu**:
     ```bash
     sudo apt update && sudo apt install ffmpeg
     ```
   - **Windows** (via [winget](https://learn.microsoft.com/windows/package-manager/winget/) ou [Chocolatey](https://chocolatey.org/)):
     ```powershell
     winget install Gyan.FFmpeg
     # ou
     choco install ffmpeg
     ```
     Confirme que o `ffmpeg` ficou no `PATH` abrindo um novo terminal e rodando `ffmpeg -version`.

2. Instale as dependências com [uv](https://docs.astral.sh/uv/) (cria o virtualenv `.venv` automaticamente):
   ```bash
   uv sync
   ```

3. Para a diarização (identificação de speakers), o pyannote exige um token do Hugging Face:
   - Crie uma conta gratuita em https://huggingface.co
   - Gere um token (read) em https://huggingface.co/settings/tokens
   - Aceite os termos dos dois modelos gated:
     - https://huggingface.co/pyannote/speaker-diarization-3.1
     - https://huggingface.co/pyannote/segmentation-3.0
   - Copie `.env.example` para `.env` e cole seu token em `HF_TOKEN`

## Autenticação e acesso

Antes de iniciar a API, defina `JWT_SECRET` no `.env` com um segredo aleatório de pelo menos 32 bytes. Não há segredo padrão. A CLI e os processos de inferência/notificação não exigem JWT_SECRET.

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM` e, quando exigidos pelo provedor, `SMTP_USER`/`SMTP_PASSWORD`. `SMTP_SECURITY=starttls` é o padrão; use `ssl` para TLS implícito (normalmente porta 465). `none` deve ser escolhido explicitamente para um servidor local de desenvolvimento. Há timeout configurável em `SMTP_TIMEOUT_SECONDS`.

Solicite o token por e-mail:

```bash
curl -X POST http://localhost:8000/auth/request-code \
  -H "Content-Type: application/json" \
  -d '{"email":"seu-email@exemplo.com"}'
```

A resposta confirma a aceitação pelo SMTP; ela não contém o token. Sem SMTP configurado ou quando o envio falha, retorna `503`. Pedidos são limitados por e-mail e IP (`429` com `Retry-After`): por padrão, 3 por e-mail e 20 por IP a cada 15 minutos. Com PostgreSQL, o limite é compartilhado entre réplicas; sem banco, é limitado por processo.

Informe o token recebido em todas as requisições de transcrição, consulta e download:

```bash
export TAP_TOKEN='token-recebido-por-email'
```

Os tokens duram 24 horas por padrão. O e-mail validado do token é registrado como proprietário do job; outro usuário recebe `404` ao tentar consultá-lo. `/health` e `/ready` permanecem públicos. Jobs antigos sem proprietário são preservados pela migração e não ficam expostos pela API.

## Testes

A suíte usa `pytest` + `pytest-cov`. Os modelos de ML (Whisper/Pyannote) e o `ffmpeg` são *stubados* nos testes — nenhum download de modelo, chamada de rede ou binário externo é necessário para rodá-la.

```bash
uv run pytest
```

Isso já roda com cobertura habilitada (configurado em `pyproject.toml`): um resumo aparece no terminal e um relatório HTML detalhado é gerado em `htmlcov/index.html`.

Para desenvolver e testar sem instalar Torch, Whisper ou Pyannote, use o grupo leve de desenvolvimento. Os testes substituem também os leitores de áudio e as chamadas ao storage:

```bash
uv sync --locked --only-group dev
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest
```

Use `uv run --no-sync ruff format .` para formatar. Antes de executar transcrições reais, rode `uv sync --locked` para instalar novamente as dependências de execução. A CI executa lint, formatação e testes com Python 3.13.

O smoke test marcado como `integration` valida a conversão real quando ffmpeg está instalado; caso contrário, ele é ignorado. Use `uv run --no-sync pytest -m "not integration"` para executar somente os testes sem ferramentas externas.

Para integração com serviços reais, use um banco PostgreSQL **exclusivo de testes** (a fixture limpa `tap_jobs` e `tap_auth_limits`) e um endpoint MinIO. O teste cria e remove um bucket temporário:

```bash
TAP_TEST_DATABASE_URL=postgresql://tap_test:tap_test@localhost:55432/tap_test \
TAP_TEST_MINIO_ENDPOINT=localhost:59000 \
TAP_TEST_MINIO_ACCESS_KEY=tap_test \
TAP_TEST_MINIO_SECRET_KEY=tap_test_secret \
uv run --no-sync pytest
```

Sem essas variáveis, testes de infraestrutura são ignorados. A CI fornece ambos os serviços e verifica recuperação após encerramento abrupto de um worker; a inferência nesse teste é simulada.

## Uso via CLI

```bash
uv run transcribe.py caminho/para/audio.mp3
```

Opções:

```bash
uv run transcribe.py audio.mp3 \
  --model medium \        # tiny/base/small/medium/large-v3 (maior = mais preciso e mais lento)
  --language pt \         # omita para detecção automática
  --device cpu \          # ou cuda (GPU NVIDIA) / mps (GPU Apple Silicon via Metal — só acelera a diarização)
  --output resultado      # gera resultado.txt e resultado.json
```

Para pular a identificação de speakers (não precisa de token do HF):

```bash
uv run transcribe.py audio.mp3 --no-diarization
```

## Servidor HTTP

`server.py` expõe a transcrição via API autenticada (FastAPI + uvicorn). Prepare JWT_SECRET e SMTP conforme [Autenticação e acesso](#autenticação-e-acesso). O modelo Whisper e o pipeline de diarização são carregados uma vez e reaproveitados entre requisições — a primeira chamada é mais lenta (carrega o modelo), as seguintes já respondem com o modelo "quente".

### Rodando por sistema operacional

O comando base é sempre o mesmo; o que muda é como cada SO/terminal seta variáveis de ambiente para escolher o `WHISPER_DEVICE` (só necessário se quiser usar GPU — sem isso, roda em CPU).

**macOS** (bash/zsh):

```bash
# CPU (default)
uv run uvicorn server:app --host 0.0.0.0 --port 8000

# GPU via Metal (Apple Silicon) — só acelera a diarização, o Whisper continua em CPU (ver tabela abaixo)
WHISPER_DEVICE=mps uv run uvicorn server:app --host 0.0.0.0 --port 8000
```

**Linux** (bash/zsh):

```bash
# CPU (default)
uv run uvicorn server:app --host 0.0.0.0 --port 8000

# GPU NVIDIA (requer driver CUDA instalado)
WHISPER_DEVICE=cuda uv run uvicorn server:app --host 0.0.0.0 --port 8000
```

**Windows** (PowerShell):

```powershell
# CPU (default)
uv run uvicorn server:app --host 0.0.0.0 --port 8000

# GPU NVIDIA (requer driver CUDA instalado)
$env:WHISPER_DEVICE = "cuda"
uv run uvicorn server:app --host 0.0.0.0 --port 8000
```

**Windows** (cmd.exe):

```bat
:: CPU (default)
uv run uvicorn server:app --host 0.0.0.0 --port 8000

:: GPU NVIDIA (requer driver CUDA instalado)
set WHISPER_DEVICE=cuda
uv run uvicorn server:app --host 0.0.0.0 --port 8000
```

> Alternativa a setar a variável na linha de comando: copie `.env.example` para `.env` e defina `WHISPER_DEVICE` lá — é lido automaticamente em qualquer SO, inclusive no Windows.

Configuração via variáveis de ambiente, também lidas do `.env`. PostgreSQL e MinIO são obrigatórios para a API assíncrona; para usar somente a CLI/rota síncrona sem banco, deixe `JOBS_DATABASE_URL` vazio:

| Variável | Default | Descrição |
|---|---|---|
| `WHISPER_MODEL` | `small` | Tamanho do modelo Whisper (tiny/base/small/medium/large-v3) |
| `WHISPER_DEVICE` | `cpu` | `cpu`, `cuda` (GPU NVIDIA) ou `mps` (GPU Apple Silicon via Metal — CTranslate2 não suporta MPS, então só a diarização roda na GPU; o Whisper continua em CPU/int8) |
| `WHISPER_LANGUAGE` | detecção automática | Código do idioma (ex: `pt`) |
| `HF_TOKEN` | — | Se definido, habilita a diarização; se ausente, o servidor transcreve normalmente sem identificar speakers |
| `MINIO_ENDPOINT` | — | Endpoint do MinIO/S3 (ex: `localhost:9000`). Obrigatório para a API assíncrona; entradas e resultados ficam no bucket compartilhado |
| `MINIO_ACCESS_KEY` | — | Access key do MinIO/S3 |
| `MINIO_SECRET_KEY` | — | Secret key do MinIO/S3 |
| `MINIO_BUCKET` | `audio-to-text` | Bucket onde o resultado dos jobs assíncronos é gravado (criado automaticamente se não existir) |
| `MINIO_SECURE` | `false` | `true` para usar TLS (HTTPS) na conexão com o MinIO/S3 |
| `MAX_UPLOAD_BYTES` | `104857600` | Limite de upload (100 MiB), conferido durante o streaming mesmo sem `Content-Length` |
| `MAX_PENDING_JOBS` | `8` | Máximo de uploads/transcrições síncronas simultâneos por processo da API |
| `FFMPEG_TIMEOUT_SECONDS` | `300` | Tempo máximo de conversão do áudio pelo ffmpeg |
| `JOB_TTL_SECONDS` | `3600` | Retenção dos metadados no banco após conclusão ou falha definitiva |
| `JOB_CLEANUP_INTERVAL_SECONDS` | `60` | Intervalo entre limpezas dos metadados expirados |
| `JOBS_DATABASE_URL` | — | URL PostgreSQL compartilhada pela API e pelos workers |
| `MAX_QUEUED_JOBS` | `100` | Limite global de jobs pendentes, contando fila e processamento |
| `JOB_MAX_ATTEMPTS` | `3` | Máximo de tentativas por job, incluindo recuperação após quedas |
| `JOB_LEASE_SECONDS` | `60` | Validade da reserva de um job pelo worker |
| `JOB_HEARTBEAT_SECONDS` | `10` | Intervalo de renovação; deve ser menor que a reserva |
| `JOB_RETRY_SECONDS` | `5` | Base do intervalo exponencial entre tentativas, limitado a 300s |
| `WORKER_POLL_SECONDS` | `1` | Espera do worker quando não há jobs disponíveis |
| `API_ASYNC_ONLY` | `false` | Desabilita inferência local; `Dockerfile.api` e Compose definem `true` |
| `JWT_SECRET` | — | Segredo de assinatura obrigatório, com pelo menos 32 bytes aleatórios |
| `JWT_TTL_SECONDS` | `86400` | Validade dos tokens de acesso |
| `AUTH_WINDOW_SECONDS` | `900` | Janela dos limites de pedidos de acesso |
| `AUTH_MAX_REQUESTS` | `3` | Pedidos de acesso por e-mail em cada janela |
| `AUTH_IP_MAX_REQUESTS` | `20` | Pedidos de acesso por IP em cada janela |
| `SMTP_HOST` | — | Servidor para códigos de acesso e transcrições |
| `SMTP_PORT` | `587` | Porta SMTP |
| `SMTP_USER` / `SMTP_PASSWORD` | — | Credenciais SMTP, informadas juntas |
| `SMTP_FROM` | `nao-responda@exemplo.com` | Remetente das mensagens |
| `SMTP_SECURITY` | `starttls` | `starttls`, `ssl` ou `none` explícito |
| `SMTP_TIMEOUT_SECONDS` | `30` | Timeout de operações SMTP |

As configurações são carregadas antes da inicialização do storage; variáveis do ambiente têm precedência sobre `.env`. Limites devem ser inteiros positivos. Uploads excessivos retornam `413`; falta de capacidade retorna `503` com `Retry-After`.

### Endpoints

- `GET /health` — liveness, retorna `{"status": "ok"}`.
- `GET /ready` — prontidão; verifica PostgreSQL e MinIO quando a fila está configurada.
- `POST /transcricao/{formato}` — recebe o áudio (mp3, wav, etc.) como corpo bruto da requisição e devolve o arquivo com a transcrição. `formato` é `txt` ou `json` (qualquer outro valor retorna `422`).

Exemplo com `curl`:

```bash
# Transcrição em texto legível
curl -X POST \
  --data-binary @audio.mp3 \
  -H "Authorization: Bearer $TAP_TOKEN" \
  -H "Content-Type: audio/mpeg" \
  http://localhost:8000/transcricao/txt \
  -o resultado.txt

# Transcrição estruturada em JSON
curl -X POST \
  --data-binary @audio.mp3 \
  -H "Authorization: Bearer $TAP_TOKEN" \
  -H "Content-Type: audio/mpeg" \
  http://localhost:8000/transcricao/json \
  -o resultado.json
```

> `--data-binary` envia o arquivo como está, sem o `curl` reformatar quebras de linha — não use `-d`/`--data` para isso.

### API Assíncrona (Arquivos Grandes)

A API assíncrona exige `JOBS_DATABASE_URL`, `MINIO_ENDPOINT` e pelo menos um worker ativo. Não há fallback em memória. A CLI e a rota síncrona das imagens completas continuam disponíveis sem PostgreSQL.

A API recebe o áudio por streaming, grava no MinIO e insere um job na fila PostgreSQL. O registro e o enfileiramento são uma única transação. A API só confirma a submissão após o commit; nenhum modelo é executado nessa rota.

1. **Despachar o job**:
   ```bash
   curl -X POST --data-binary @audio.mp3 -H "Content-Type: audio/mpeg" \
     -H "Authorization: Bearer $TAP_TOKEN" \
     http://localhost:8000/async/transcricao/txt
   ```
   O contrato existente é preservado: HTTP `200` com `{"job_id": "...", "status": "processing"}`. Internamente, o estado inicial é `queued`.

2. **Consultar ou baixar o resultado**:
   ```bash
   curl -H "Authorization: Bearer $TAP_TOKEN" -JLO http://localhost:8000/async/status/{job_id}
   ```
   Jobs em fila ou execução retornam JSON com `processing`. Ao concluir, a mesma rota retorna o arquivo; uma falha definitiva retorna `500` com mensagem genérica.

3. **Executar o worker fora de contêiner**:
   ```bash
   uv sync --locked
   uv run python -m worker
   ```
   Use as mesmas configurações de PostgreSQL e MinIO da API. Para diarização, injete `HF_TOKEN` tanto na API quanto no worker; credenciais não são persistidas no job. Modelo, idioma e opção de diarização são registrados na submissão. `WHISPER_DEVICE` é definido em cada worker.

Cada worker reserva um job, renova a reserva durante a inferência e confirma a conclusão com seu token. Se morrer, outro worker recupera a reserva vencida e repete o processamento. As tentativas são limitadas e usam espera exponencial. Resultados têm uma chave por tentativa: workers antigos não sobrescrevem o resultado vigente. A execução é **pelo menos uma vez**, sem promessa de execução única; reenviar o POST cria outro job.

O resultado pode ser baixado repetidamente durante `JOB_TTL_SECONDS`. Depois do prazo, retorna `410` até a remoção dos metadados e `404` após a limpeza. Configure lifecycle do bucket para expurgar áudios, resultados e uploads órfãos, com prazo suficiente para fila, tentativas e retenção. Em falha ambígua no commit, o upload é preservado para não quebrar um job já confirmado.

Quando SMTP está configurado na submissão, o job também registra uma notificação pendente para o proprietário. O processo `uv run python -m notifications` baixa o resultado e envia o anexo, com reserva e tentativas independentes. Falhas SMTP não reexecutam a inferência e não retiram o resultado do estado `completed`. O Compose inicia esse processo automaticamente. Se SMTP estiver ausente no notificador, as notificações aguardam configuração até a retenção do job.

A entrega de e-mail é pelo menos uma vez: uma queda após aceitação pelo SMTP, antes da confirmação no banco, pode causar reenvio. O Message-ID é estável por job, sem garantia de deduplicação pelo provedor. A expiração do job também encerra a janela de entrega.

As migrações em `migrations/` são aplicadas automaticamente na inicialização da API e dos workers, sob trava PostgreSQL. Use volume persistente e backups para PostgreSQL e MinIO. Detalhes em [docs/DAS.md](docs/DAS.md) e na [ADR-0001](docs/adr/0001-fila-duravel-de-transcricao-no-postgresql.md).

A documentação interativa (Swagger UI) completa fica disponível em `http://localhost:8000/docs`.

## Performance: CPU vs GPU (Metal)

Comparativo transcrevendo o mesmo áudio (~324KB) via `curl --data-binary` contra `/transcricao/txt`, rodando o servidor em macOS com CPU (default) vs `WHISPER_DEVICE=mps` (GPU Apple Silicon via Metal — acelera só a etapa de diarização, ver [Rodando por sistema operacional](#servidor-http)).

**CPU** (`WHISPER_DEVICE=cpu`, default)

![Performance CPU](./img/performance-cpu.png)

```
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100  325k  100  1172  100  324k     15   4370  0:01:18  0:01:15  0:00:03   259
```

**GPU — Metal** (`WHISPER_DEVICE=mps`)

![Performance GPU Metal](./img/performance-gpu.png)

```
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100  325k  100  1172  100  324k     47  13375  0:00:24  0:00:24 --:--:--   257
```

Tempo total caiu de **1m18s para 24s** (~3,25x mais rápido) só acelerando a diarização via Metal — em áudios mais longos, onde a diarização pesa proporcionalmente mais, o ganho tende a ser ainda maior.

## Docker

As imagens CPU/GPU completas rodam o servidor HTTP por padrão (`ENTRYPOINT` = uvicorn, porta `8000`) e também podem executar o worker:

- `Dockerfile.api`: API assíncrona leve, sem Torch/Whisper/Pyannote; a rota síncrona retorna `503`.
- `Dockerfile.minio`: compila uma release fixa do código oficial do MinIO Community, pois as imagens públicas anteriores deixaram de estar disponíveis.
- `Dockerfile.cpu`: usa a build CPU-only do PyTorch, mais leve. Use quando os nós não têm GPU.
- `Dockerfile.gpu`: usa a build do PyTorch com suporte CUDA. Requer nó com GPU NVIDIA, driver instalado e `--gpus all` (Docker) ou NVIDIA device plugin (k8s).

Build:

```bash
docker build -f Dockerfile.cpu -t audio-to-text:cpu .
# ou
docker build -f Dockerfile.gpu -t audio-to-text:gpu .
```

Executar localmente (CPU):

```bash
docker run --rm -p 8000:8000 \
  --env-file .env -e JOBS_DATABASE_URL= -e MINIO_ENDPOINT= \
  audio-to-text:cpu
```

Executar localmente (GPU):

```bash
docker run --rm --gpus all -p 8000:8000 \
  --env-file .env -e JOBS_DATABASE_URL= -e MINIO_ENDPOINT= \
  -e WHISPER_DEVICE=cuda \
  audio-to-text:gpu
```

Com o container no ar, os mesmos exemplos de `curl` da seção [Servidor HTTP](#servidor-http) funcionam apontando para `http://localhost:8000`.

Para rodar a CLI dentro do container em vez do servidor (por exemplo, num Job do k8s processando um áudio de um volume montado), sobrescreva o entrypoint:

```bash
docker run --rm --entrypoint python -v "$PWD/dados:/data" \
  audio-to-text:cpu transcribe.py /data/audio.mp3 --output /data/resultado
```

### Docker Compose (API, worker, PostgreSQL e MinIO)

O Compose sobe a API leve, um worker CPU, um notificador, PostgreSQL e MinIO, com volumes para os dados persistentes. O primeiro build do MinIO compila o código oficial da release `RELEASE.2025-10-15T17-29-55Z` ([fonte e licença](https://github.com/minio/minio/tree/RELEASE.2025-10-15T17-29-55Z)).

```bash
# Se .env ainda não existir, copie .env.example; preencha JWT_SECRET e SMTP antes de iniciar.
docker compose up --build
```

- API assíncrona e Swagger: `http://localhost:8000` e `/docs`.
- MinIO: S3 em `http://localhost:9000`; console em `http://localhost:9001`.
- PostgreSQL: `localhost:5432`; credenciais locais no `.env.example`.
- Para adicionar consumidores: `docker compose up -d --scale worker=2`.

A imagem leve não atende transcrição síncrona. Para manter essa rota, execute uma imagem CPU/GPU completa com `API_ASYNC_ONLY=false`, conforme os exemplos anteriores. Os serviços recebem as mesmas configurações de banco e storage; jobs sobrevivem à troca de processos e contêineres, desde que os volumes permaneçam. Não remova volumes ao reiniciar o ambiente se precisar preservar trabalhos.

### OpenShift (Knative Serving)

Aplique `knative-service.yaml` para a API leve e **um** dos deployments em `deploy/worker-cpu.yaml` ou `deploy/worker-gpu.yaml`, após ajustar as imagens. Configure o Secret `tap-runtime` com `JWT_SECRET`, `JOBS_DATABASE_URL`, `MINIO_ENDPOINT`, credenciais, bucket, TLS, variáveis SMTP e `HF_TOKEN` quando necessário. Aplique também o deployment de notificações. PostgreSQL e storage devem ser compartilhados e persistentes.

```bash
oc apply -f knative-service.yaml
oc apply -f deploy/worker-cpu.yaml
oc apply -f deploy/notifications.yaml
```

A API pode escalar a zero e ter várias réplicas. Workers são Deployments independentes, sem scale-to-zero por ausência de tráfego HTTP. Cada processo executa uma inferência por vez; para GPU, reserve uma GPU por pod. Em encerramento normal, o worker tenta concluir o trabalho atual; em queda abrupta, a reserva expira e outro worker o retoma.

## Saída

Mesmo formato tanto na CLI (`<nome>.txt`/`<nome>.json`) quanto no servidor HTTP (`resultado.txt`/`resultado.json` devolvido no corpo da resposta):

- `.txt`: transcrição legível, uma linha por segmento, ex:
  ```text
  [pessoa1] 00:00:00 - 00:00:04: Olá, tudo bem?
  [pessoa2] 00:00:05 - 00:00:08: Tudo ótimo, e você?
  ```
- `.json`: os mesmos segmentos em formato estruturado (`start`, `end`, `text`, `speaker`). Exemplo:
  ```json
  [
    {
      "start": 0.0,
      "end": 4.0,
      "text": " Olá, tudo bem?",
      "speaker": "pessoa1"
    },
    {
      "start": 5.0,
      "end": 8.0,
      "text": " Tudo ótimo, e você?",
      "speaker": "pessoa2"
    }
  ]
  ```

## Troubleshooting / FAQ

**1. Erro de autenticação/acesso negado no HuggingFace**
- **Sintoma**: Erros como `HTTPError: 401 Client Error` ou `403 Forbidden` ao inicializar a diarização (Pyannote).
- **Solução**: Você precisa criar uma conta no HuggingFace, gerar um Token (Read), e **aceitar os termos de uso** nos dois modelos exigidos na documentação ([segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) e [speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)). Certifique-se de que a variável `HF_TOKEN` está configurada corretamente no `.env` ou ambiente.

**2. O comando falha indicando que `ffmpeg` não foi encontrado**
- **Sintoma**: `FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'`
- **Solução**: O pacote Python não embute os binários do FFmpeg. Você precisa instalá-lo no nível do sistema operacional (via `brew`, `dnf`, `apt`, etc.) e garantir que o binário `ffmpeg` esteja acessível no seu `PATH`.

**3. Falta de memória na GPU (CUDA OOM - Out of Memory)**
- **Sintoma**: Erro `RuntimeError: CUDA out of memory` ao tentar transcrever um áudio via servidor ou CLI.
- **Solução**: O modelo Whisper tem variações de tamanho. O `large-v3` ou mesmo o `medium` podem consumir mais VRAM do que a sua placa gráfica possui. Tente utilizar um modelo menor passando a opção `--model small` ou `--model base` na CLI, ou alterando a variável de ambiente `WHISPER_MODEL=small` no servidor.

## Contribuidores

Obrigado a todas as pessoas que já contribuíram com o T.A.P.! 🍺

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/caiocolares">
        <img src="https://github.com/caiocolares.png" width="100" alt="Caio Colares"><br>
        <sub><b>Caio Colares</b></sub>
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/rafaelsreis">
        <img src="https://github.com/rafaelsreis.png" width="100" alt="Rafael Reis"><br>
        <sub><b>Rafael Reis</b></sub>
      </a>
    </td>
  </tr>
</table>

Quer aparecer nessa lista? Veja o [CONTRIBUTING.md](./CONTRIBUTING.md) e as [good first issues](./GOOD-FIRST-ISSUES.md).

---

<div align="center">

### DTec OpenLabs

*Inovação aberta, soluções reais e engenharia na prática.*

Feito com 🍺 por [Caio Colares](https://github.com/caiocolares)

[Reportar um problema](https://github.com/caiocolares/tap/issues) · [faster-whisper](https://github.com/SYSTRAN/faster-whisper) · [pyannote.audio](https://github.com/pyannote/pyannote-audio)

</div>
