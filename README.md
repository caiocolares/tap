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

  ### Transcrição de áudio com IA — extraindo falas e separando palestrantes.
</div>

O T.A.P. é um motor inteligente para transformar arquivos de áudio em diálogos estruturados. Ele utiliza o [faster-whisper](https://github.com/SYSTRAN/faster-whisper) para reconhecer as falas e o [pyannote.audio](https://github.com/pyannote/pyannote-audio) para a "diarização" (sinalizando a troca de palestrantes como `pessoa1`, `pessoa2`).

---

<<<<<<< HEAD
- [Escopo](#escopo)
- [Setup](#setup)
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
=======
## 📖 Índice
>>>>>>> origin/develop

- [1. Consumindo a API (Integração)](#1-consumindo-a-api-integração)
  - [Autenticação](#autenticação)
  - [Transcrição (Síncrona)](#transcrição-síncrona)
  - [Transcrição de Arquivos Grandes (Assíncrona)](#transcrição-de-arquivos-grandes-assíncrona)
  - [Formato da Saída](#formato-da-saída)
- [2. Configuração e Infraestrutura (Deploy)](#2-configuração-e-infraestrutura-deploy)
  - [Variáveis de Ambiente](#variáveis-de-ambiente)
  - [Docker e Docker Compose](#docker-e-docker-compose)
  - [OpenShift (Knative)](#openshift-knative)
- [3. Instalação Local e CLI (Desenvolvedores)](#3-instalação-local-e-cli-desenvolvedores)
- [4. Performance: CPU vs GPU](#4-performance-cpu-vs-gpu)
- [5. Troubleshooting / FAQ](#5-troubleshooting--faq)
- [6. Contribuidores](#6-contribuidores)

---

## 1. Consumindo a API (Integração)

A principal forma de utilizar o T.A.P. é através de sua API REST. O serviço expõe rotas otimizadas tanto para áudios curtos quanto para gravações longas. A documentação interativa (Swagger UI) está sempre disponível acessando `/docs` no seu servidor (ex: `http://localhost:8000/docs`).

### Autenticação

Nossa API é protegida por tokens criptográficos (JWT). Você nunca precisará memorizar senhas. Basta solicitar um código de acesso para o seu e-mail, e ele valerá por 24 horas.

**Passo 1: Peça o seu código de acesso**
```bash
curl -X POST http://localhost:8000/auth/request-code \
  -H "Content-Type: application/json" \
  -d '{"email": "seu.email@exemplo.com"}'
```
Você receberá em segundos um e-mail contendo o seu token.

### Transcrição (Síncrona)

<<<<<<< HEAD
Para desenvolver e testar sem instalar Torch, Whisper ou Pyannote, use o grupo leve de desenvolvimento. Os testes substituem também os leitores de áudio e as chamadas ao storage:

```bash
uv sync --locked --only-group dev
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest
```

Use `uv run --no-sync ruff format .` para formatar. Antes de executar transcrições reais, rode `uv sync --locked` para instalar novamente as dependências de execução. A CI executa lint, formatação e testes com Python 3.13.

O smoke test marcado como `integration` valida a conversão real quando ffmpeg está instalado; caso contrário, ele é ignorado. Use `uv run --no-sync pytest -m "not integration"` para executar somente os testes sem ferramentas externas.

Para integração com serviços reais, use um banco PostgreSQL **exclusivo de testes** (a fixture limpa `tap_jobs`) e um endpoint MinIO. O teste cria e remove um bucket temporário:

```bash
TAP_TEST_DATABASE_URL=postgresql://tap_test:tap_test@localhost:55432/tap_test \
TAP_TEST_MINIO_ENDPOINT=localhost:59000 \
TAP_TEST_MINIO_ACCESS_KEY=tap_test \
TAP_TEST_MINIO_SECRET_KEY=tap_test_secret \
uv run --no-sync pytest
```

Sem essas variáveis, testes de infraestrutura são ignorados. A CI fornece ambos os serviços e verifica recuperação após encerramento abrupto de um worker; a inferência nesse teste é simulada.

## Uso via CLI
=======
Com o seu token em mãos, você já pode solicitar transcrições. Basta anexar o áudio no corpo da requisição e enviar o seu código no cabeçalho `Authorization: Bearer <TOKEN>`.
>>>>>>> origin/develop

> **Dica**: Use `--data-binary` no cURL para enviar o arquivo bruto e sem corrompimentos.

**Exemplo para obter o texto legível (`.txt`)**
```bash
curl -X POST http://localhost:8000/transcricao/txt \
  -H "Authorization: Bearer COLE_SEU_TOKEN_AQUI" \
  -H "Content-Type: audio/mpeg" \
  --data-binary @meu_audio.mp3 \
  -o transcricao.txt
```

**Exemplo para obter dados estruturados (`.json`)**
```bash
curl -X POST http://localhost:8000/transcricao/json \
  -H "Authorization: Bearer COLE_SEU_TOKEN_AQUI" \
  -H "Content-Type: audio/mpeg" \
  --data-binary @meu_audio.mp3 \
  -o transcricao.json
```

### Transcrição de Arquivos Grandes (Assíncrona)

Para arquivos maiores que 5 minutos, conexões HTTP convencionais sofrem risco de cair por *Timeout* (fechamento forçado pelos provedores de internet). Pensando nisso, a API oferece a rota `/async/`.

Ao usar esta rota, o servidor entra no modelo **Despacha e Esquece**. O sistema começará o trabalho no servidor inteligente e **enviará o arquivo pronto para o seu e-mail** (o mesmo e-mail que você registrou no seu token).

**Despachando o trabalho:**
```bash
curl -X POST http://localhost:8000/async/transcricao/txt \
  -H "Authorization: Bearer COLE_SEU_TOKEN_AQUI" \
  -H "Content-Type: audio/mpeg" \
  --data-binary @podcast_longo.mp3
```
*Retorno*: `{"job_id": "8f3...a9b", "status": "processing"}`

Você pode aguardar que a transcrição chegue automaticamente no seu e-mail, ou verificar o status manualmente:
```bash
curl -JLO http://localhost:8000/async/status/{job_id}
```

### Formato da Saída

A plataforma devolve o arquivo com marcações para identificar o turno de cada falante.

**Formato legível (.txt)**: ideal para leitura humana.
```text
[pessoa1] 00:00:00 - 00:00:04: Olá, tudo bem?
[pessoa2] 00:00:05 - 00:00:08: Tudo ótimo, e você?
```

**Formato estruturado (.json)**: ideal para painéis de BI, robôs e ingestão por outras IAs.
```json
[
  {
    "start": 0.0,
    "end": 4.0,
    "text": " Olá, tudo bem?",
    "speaker": "pessoa1"
  }
]
```

---

## 2. Configuração e Infraestrutura (Deploy)

Esta seção é dedicada a quem vai hospedar e gerenciar a aplicação nos servidores.

### Variáveis de Ambiente

<<<<<<< HEAD
Configuração via variáveis de ambiente, também lidas do `.env`. PostgreSQL e MinIO são obrigatórios para a API assíncrona; para usar somente a CLI/rota síncrona sem banco, deixe `JOBS_DATABASE_URL` vazio:
=======
Crie o arquivo `.env` (use `.env.example` como base). Todas são opcionais, exceto tokens externos.
>>>>>>> origin/develop

| Variável | Default | Descrição |
|---|---|---|
| `JWT_SECRET` | `super-secreto...` | **[CRÍTICO]** Chave secreta usada para assinar os tokens de autorização. Mude em produção! |
| `WHISPER_MODEL` | `medium` | Tamanho do modelo Whisper (tiny/base/small/medium/large-v3) |
<<<<<<< HEAD
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

As configurações são carregadas antes da inicialização do storage; variáveis do ambiente têm precedência sobre `.env`. Limites devem ser inteiros positivos. Uploads excessivos retornam `413`; falta de capacidade retorna `503` com `Retry-After`.
=======
| `WHISPER_DEVICE` | `cpu` | `cpu`, `cuda` (NVIDIA) ou `mps` (Apple Silicon — GPU acelera apenas a diarização) |
| `HF_TOKEN` | — | Token do HuggingFace. **Habilita a identificação de pessoas**. Se omitido, ele apenas transcreve sem nomear palestrantes. |
| `SMTP_HOST` | — | Host do servidor SMTP para envio das transcrições e tokens por e-mail |
| `SMTP_PORT` | `587` | Porta do servidor SMTP |
| `SMTP_USER` | — | Usuário para autenticação SMTP |
| `SMTP_PASSWORD` | — | Senha para autenticação SMTP |
| `SMTP_FROM` | `nao-responda...` | Endereço de remetente para e-mails disparados |
| `MINIO_ENDPOINT` | — | Endpoint do MinIO/S3. Se omitido, jobs assíncronos ficam salvos no disco local do container. |
| `MINIO_ACCESS_KEY` | — | Access key do MinIO/S3 |
| `MINIO_SECRET_KEY` | — | Secret key do MinIO/S3 |
| `MINIO_BUCKET` | `audio-to-text` | Bucket de destino dos processamentos assíncronos |
>>>>>>> origin/develop

### Docker e Docker Compose

<<<<<<< HEAD
- `GET /health` — liveness, retorna `{"status": "ok"}`.
- `GET /ready` — prontidão; verifica PostgreSQL e MinIO quando a fila está configurada.
- `POST /transcricao/{formato}` — recebe o áudio (mp3, wav, etc.) como corpo bruto da requisição e devolve o arquivo com a transcrição. `formato` é `txt` ou `json` (qualquer outro valor retorna `422`).
=======
Fornecemos builds otimizadas para processadores convencionais (`Dockerfile.cpu`) e servidores de altíssimo rendimento (`Dockerfile.gpu`).
>>>>>>> origin/develop

Para subir o sistema rapidamente com suporte já configurado para MinIO (Object Storage S3):
```bash
# 1. Ajuste os segredos no arquivo `.env`
cp .env.example .env

# 2. Inicialize a Stack
docker compose up --build -d
```
O servidor web da API estará disponível em `http://localhost:8000` e o console do Object Storage S3 em `http://localhost:9001`.

### OpenShift (Knative)

`knative-service.yaml` traz os recursos `serving.knative.dev/v1 Service` prontos para deploy Serverless via Kubernetes/OpenShift (tirando proveito de **scale-to-zero** quando a IA está ociosa).

```bash
<<<<<<< HEAD
# Transcrição em texto legível
curl -X POST \
  --data-binary @audio.mp3 \
  -H "Content-Type: audio/mpeg" \
  http://localhost:8000/transcricao/txt \
  -o resultado.txt

# Transcrição estruturada em JSON
curl -X POST \
  --data-binary @audio.mp3 \
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
     http://localhost:8000/async/transcricao/txt
   ```
   O contrato existente é preservado: HTTP `200` com `{"job_id": "...", "status": "processing"}`. Internamente, o estado inicial é `queued`.

2. **Consultar ou baixar o resultado**:
   ```bash
   curl -JLO http://localhost:8000/async/status/{job_id}
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
  -e HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx \
  audio-to-text:cpu
```

Executar localmente (GPU):

```bash
docker run --rm --gpus all -p 8000:8000 \
  -e HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx \
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

O Compose sobe a API leve, um worker CPU, PostgreSQL e MinIO, com volumes para os dados persistentes. O primeiro build do MinIO compila o código oficial da release `RELEASE.2025-10-15T17-29-55Z` ([fonte e licença](https://github.com/minio/minio/tree/RELEASE.2025-10-15T17-29-55Z)).

```bash
# Se .env ainda não existir, copie .env.example e ajuste os valores.
docker compose up --build
```

- API assíncrona e Swagger: `http://localhost:8000` e `/docs`.
- MinIO: S3 em `http://localhost:9000`; console em `http://localhost:9001`.
- PostgreSQL: `localhost:5432`; credenciais locais no `.env.example`.
- Para adicionar consumidores: `docker compose up -d --scale worker=2`.

A imagem leve não atende transcrição síncrona. Para manter essa rota, execute uma imagem CPU/GPU completa com `API_ASYNC_ONLY=false`, conforme os exemplos anteriores. Os serviços recebem as mesmas configurações de banco e storage; jobs sobrevivem à troca de processos e contêineres, desde que os volumes permaneçam. Não remova volumes ao reiniciar o ambiente se precisar preservar trabalhos.

### OpenShift (Knative Serving)

Aplique `knative-service.yaml` para a API leve e **um** dos deployments em `deploy/worker-cpu.yaml` ou `deploy/worker-gpu.yaml`, após ajustar as imagens. Configure o Secret `tap-runtime` com `JOBS_DATABASE_URL`, `MINIO_ENDPOINT`, credenciais, bucket, TLS e `HF_TOKEN` quando necessário. PostgreSQL e storage devem ser compartilhados e persistentes.

```bash
=======
oc create secret generic audio-to-text-hf-token --from-literal=HF_TOKEN=hf_xxx
>>>>>>> origin/develop
oc apply -f knative-service.yaml
oc apply -f deploy/worker-cpu.yaml
```

<<<<<<< HEAD
A API pode escalar a zero e ter várias réplicas. Workers são Deployments independentes, sem scale-to-zero por ausência de tráfego HTTP. Cada processo executa uma inferência por vez; para GPU, reserve uma GPU por pod. Em encerramento normal, o worker tenta concluir o trabalho atual; em queda abrupta, a reserva expira e outro worker o retoma.

## Saída
=======
---
>>>>>>> origin/develop

## 3. Instalação Local e CLI (Desenvolvedores)

Se você deseja debugar os modelos localmente sem usar Docker ou containers:

1. **Dependências do Sistema**: O software requer a biblioteca base do `ffmpeg`. Instale no seu SO (ex: `brew install ffmpeg` no Mac ou `sudo apt install ffmpeg` no Ubuntu).
2. **Ambiente Python**: Instale os pacotes com [uv](https://docs.astral.sh/uv/):
   ```bash
   uv sync
   ```
3. **Uso via Linha de Comando**:
   O `transcribe.py` pode ser executado diretamente para bater nos modelos de inteligência sem passar por requisições HTTP:
   ```bash
   uv run transcribe.py audio.mp3 --output resultado
   ```
   > Parâmetros adicionais incluem `--model`, `--language`, `--device` e `--no-diarization`. Digite `uv run transcribe.py --help` para ver a lista completa.

**Testes Automatizados:**
A base do projeto utiliza testes _stubados_ que isolam o FFmpeg e a Rede.
```bash
uv run pytest
```

---

## 4. Performance: CPU vs GPU

O servidor opera perfeitamente sem placas de vídeo (o que facilita imensamente o deploy em pods Cloud genéricos). Porém, em hardwares com aceleração, o tempo desaba. Exemplo de processamento de áudio com as configurações nativas no Mac:

- **Somente CPU (`WHISPER_DEVICE=cpu`)**: Tempo total **1m18s**
- **Aceleração Apple Metal (`WHISPER_DEVICE=mps`)**: Tempo total **24s** (3.2x mais rápido)

---

## 5. Troubleshooting / FAQ

**Erro `401 Unauthorized` na API:**
Você precisa informar o cabeçalho HTTP: `Authorization: Bearer <seu_token>`. Gere um token de 24 horas usando o endpoint `/auth/request-code`.

**Erro de acesso no HuggingFace (`401` ou `403` nos logs):**
O motor de separação de palestrantes requer aceitar um termo de uso gratuito. Crie sua conta, vá em [segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) e [speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) para assinar o termo, e gere um *Token Read*. Adicione esse token no `.env` como `HF_TOKEN`.

**Erro `FileNotFoundError: No such file or directory: 'ffmpeg'`**
O binário do FFmpeg não está instalado na máquina base. Instale-o a nível de Sistema Operacional. No container Docker, nós já resolvemos isso por você.

**Erro `RuntimeError: CUDA out of memory`**
Sua GPU (placa de vídeo) não tem VRAM suficiente para rodar o modelo configurado (`medium` ou `large-v3`). Abaixe o modelo ajustando a variável `.env` para `WHISPER_MODEL=small` ou `base`.

---

## 6. Contribuidores

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

</div>
