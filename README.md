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

## 📖 Índice

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

Com o seu token em mãos, você já pode solicitar transcrições. Basta anexar o áudio no corpo da requisição e enviar o seu código no cabeçalho `Authorization: Bearer <TOKEN>`.

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

Crie o arquivo `.env` (use `.env.example` como base). Todas são opcionais, exceto tokens externos.

| Variável | Default | Descrição |
|---|---|---|
| `JWT_SECRET` | `super-secreto...` | **[CRÍTICO]** Chave secreta usada para assinar os tokens de autorização. Mude em produção! |
| `WHISPER_MODEL` | `medium` | Tamanho do modelo Whisper (tiny/base/small/medium/large-v3) |
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

### Docker e Docker Compose

Fornecemos builds otimizadas para processadores convencionais (`Dockerfile.cpu`) e servidores de altíssimo rendimento (`Dockerfile.gpu`).

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
oc create secret generic audio-to-text-hf-token --from-literal=HF_TOKEN=hf_xxx
oc apply -f knative-service.yaml
oc get ksvc audio-to-text -o jsonpath='{.status.url}{"\n"}'
```

---

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
