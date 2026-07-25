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
- [Testes](#testes)
- [Uso via CLI](#uso-via-cli)
- [Servidor HTTP](#servidor-http)
  - [Endpoints](#endpoints)
  - [API Assíncrona (Arquivos Grandes)](#api-assíncrona-arquivos-grandes)
- [Performance: CPU vs GPU (Metal)](#performance-cpu-vs-gpu-metal)
- [Docker](#docker)
  - [Docker Compose (app + MinIO)](#docker-compose-app--minio)
  - [OpenShift (Knative Serving)](#openshift-knative-serving)
- [Saída](#saída)
- [Troubleshooting / FAQ](#troubleshooting--faq)

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

## Testes

A suíte usa `pytest` + `pytest-cov`. Os modelos de ML (Whisper/Pyannote) e o `ffmpeg` são *stubados* nos testes — nenhum download de modelo, chamada de rede ou binário externo é necessário para rodá-la.

```bash
uv run pytest
```

Isso já roda com cobertura habilitada (configurado em `pyproject.toml`): um resumo aparece no terminal e um relatório HTML detalhado é gerado em `htmlcov/index.html`.

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

`server.py` expõe a mesma transcrição via API (FastAPI + uvicorn). O modelo Whisper e o pipeline de diarização são carregados uma vez e reaproveitados entre requisições — a primeira chamada é mais lenta (carrega o modelo), as seguintes já respondem com o modelo "quente".

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

Configuração via variáveis de ambiente (todas opcionais, também lidas do `.env`):

| Variável | Default | Descrição |
|---|---|---|
| `WHISPER_MODEL` | `medium` | Tamanho do modelo Whisper (tiny/base/small/medium/large-v3) |
| `WHISPER_DEVICE` | `cpu` | `cpu`, `cuda` (GPU NVIDIA) ou `mps` (GPU Apple Silicon via Metal — CTranslate2 não suporta MPS, então só a diarização roda na GPU; o Whisper continua em CPU/int8) |
| `WHISPER_LANGUAGE` | detecção automática | Código do idioma (ex: `pt`) |
| `HF_TOKEN` | — | Se definido, habilita a diarização; se ausente, o servidor transcreve normalmente sem identificar speakers |
| `MINIO_ENDPOINT` | — | Endpoint do MinIO/S3 (ex: `localhost:9000`). Se ausente, o resultado dos jobs assíncronos fica só no disco local do processo |
| `MINIO_ACCESS_KEY` | — | Access key do MinIO/S3 |
| `MINIO_SECRET_KEY` | — | Secret key do MinIO/S3 |
| `MINIO_BUCKET` | `audio-to-text` | Bucket onde o resultado dos jobs assíncronos é gravado (criado automaticamente se não existir) |
| `MINIO_SECURE` | `false` | `true` para usar TLS (HTTPS) na conexão com o MinIO/S3 |

### Endpoints

- `GET /health` — liveness/readiness check, retorna `{"status": "ok"}`.
- `POST /transcricao/{formato}` — recebe o áudio (mp3, wav, etc.) como corpo bruto da requisição e devolve o arquivo com a transcrição. `formato` é `txt` ou `json` (qualquer outro valor retorna `422`).

Exemplo com `curl`:

```bash
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

Para evitar *timeouts* de conexão em áudios longos, o sistema suporta processamento assíncrono (modelo de *Polling*). O servidor agenda o trabalho em *background* e devolve um `job_id` imediatamente.

1. **Despachar o Job**:
   ```bash
   curl -X POST --data-binary @audio.mp3 -H "Content-Type: audio/mpeg" \
     http://localhost:8000/async/transcricao/txt
   ```
   *Retorno*: `{"job_id": "8f3...a9b", "status": "processing"}`

2. **Consultar o Status / Baixar o Resultado**:
   Enquanto estiver processando, o retorno será um JSON (`{"job_id": "...", "status": "processing"}`). Quando concluir, o download do arquivo inicia automaticamente.
   ```bash
   curl -JLO http://localhost:8000/async/status/{job_id}
   ```

Se `MINIO_ENDPOINT` estiver configurado, o áudio original é gravado no bucket MinIO/S3 antes de iniciar o processamento, e o resultado também é gravado lá ao final — em vez de ficarem só no disco local do processo. Ver [Docker Compose (app + MinIO)](#docker-compose-app--minio).

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

Duas imagens são fornecidas — ambas rodam o servidor HTTP por padrão (`ENTRYPOINT` = uvicorn, porta `8000`):

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

### Docker Compose (app + MinIO)

`docker-compose.yml` sobe o servidor (build de `Dockerfile.cpu`) junto com um container do [MinIO](https://min.io/) — object storage compatível com S3 usado para persistir o resultado dos jobs assíncronos (ver [API Assíncrona](#api-assíncrona-arquivos-grandes) e `TODO.md`, Nível 3).

```bash
cp .env.example .env   # se ainda não existir; preencha ao menos o HF_TOKEN
docker compose up --build
```

- App: `http://localhost:8000` (mesmos endpoints de sempre)
- Console web do MinIO: `http://localhost:9001` (login `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD`, default `minioadmin`/`minioadmin`)
- API S3 do MinIO: `http://localhost:9000`

O `docker-compose.yml` já injeta `MINIO_ENDPOINT=minio:9000` no container do `app`, então o bucket (`MINIO_BUCKET`, default `audio-to-text`) é criado automaticamente na primeira execução. Para rodar sem MinIO (comportamento original, resultado só em disco local), use `docker run` como nos exemplos acima em vez do compose.

### OpenShift (Knative Serving)

`knative-service.yaml` traz os recursos `serving.knative.dev/v1 Service` (CPU e GPU) para deploy via OpenShift Serverless — inclui autoscaling (com scale-to-zero), probes em `/health` e injeção opcional do `HF_TOKEN` via Secret. Instruções completas de pré-requisitos e uso estão nos comentários do próprio arquivo:

```bash
oc create secret generic audio-to-text-hf-token --from-literal=HF_TOKEN=hf_xxx  # opcional
oc apply -f knative-service.yaml
oc get ksvc audio-to-text -o jsonpath='{.status.url}{"\n"}'
```

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
