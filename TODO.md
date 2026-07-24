# TODO: Escalabilidade Horizontal (Múltiplos Pods)

Atualmente, o estado dos jobs assíncronos (o dicionário `_jobs`) e os arquivos temporários são armazenados na memória e no disco local do *Pod* que recebe a requisição. Se o projeto escalar para 2 ou mais Pods no OpenShift/Kubernetes, um cliente pode despachar o áudio no Pod A e o roteador enviar a requisição de polling (`GET /async/status`) para o Pod B, resultando em um erro 404 (Job não encontrado).

Abaixo estão as sugestões de arquitetura para resolver esse problema, separadas por nível de maturidade e esforço de implementação.

---

## Nível 1: Solução Rápida (Paliativa)
**Sticky Sessions (Afinidade de Sessão)**

- **Como funciona**: Configurar o Ingress/Router do OpenShift para garantir que todas as requisições de um mesmo cliente (baseadas em IP ou Cookie gerado no primeiro request) caiam sempre no mesmo Pod.
- **Prós**: Zero alteração no código Python atual. Resolve o problema do 404 no polling de forma quase imediata.
- **Contras**: Desbalanceamento de carga pesado (um Pod pode acabar recebendo 10 áudios difíceis enquanto o outro fica ocioso). Se o Pod for reiniciado pelo Kubernetes ou sofrer *scale-down*, os jobs que estavam nele são perdidos silenciosamente e o cliente jamais receberá o arquivo.
- **Implementação (OpenShift/Knative)**: Adicionar as devidas *annotations* de roteamento no YAML para forçar a afinidade.

---

## Nível 2: Solução Intermediária
**Estado em Cache Compartilhado + Storage Compartilhado**

- **Como funciona**: O dicionário `_jobs` local deixa de existir. O status é salvo em um banco chave-valor ultra-rápido, como o **Redis**. Além disso, o diretório onde o FastAPI salva o áudio temporário e o arquivo final gerado (`/tmp` atual) passa a apontar para um PVC (Persistent Volume Claim) do tipo `ReadWriteMany` (acessível simultaneamente por todos os Pods, como um NFS).
- **Prós**:
  - Pod A grava o áudio no volume, agenda a task, e anota `processing` no Redis.
  - Pod B atende a requisição de polling do cliente, lê o status do Redis e, se estiver concluído, envia o arquivo lendo diretamente do volume compartilhado.
  - O balanceamento HTTP volta a ser perfeito (round-robin).
- **Contras**: Volumes `ReadWriteMany` podem sofrer de gargalos de I/O em arquivos simultâneos pesados dependendo do hardware subjacente. A API web ainda é a mesma responsável por gastar CPU/GPU executando o modelo de ML pesado, podendo ficar travada.
- **Implementação**: Instalar o driver do `redis` no Python, substituir as leituras de dicionário e configurar o volume no `deployment.yaml`.

---

## Nível 3: Solução Definitiva (Arquitetura Corporativa)
**Desacoplamento: Mensageria (Workers) + Object Storage**

- **Como funciona**: A aplicação web (FastAPI) é completamente separada do motor de inteligência artificial (Whisper/Pyannote).
  - O cliente envia o áudio para o FastAPI, que faz *upload direto* para um **Object Storage (S3, MinIO ou Azure Blob)**.
  - O FastAPI publica uma simples mensagem JSON (ex: `"Processar arquivo X.mp3 com job_id Y"`) em uma fila de **Mensageria (RabbitMQ, Kafka, Celery)** e grava o status no banco/Redis.
  - Outro deployment (os **Workers**) consome essa fila, baixa o arquivo do S3, usa a GPU para transcrição, faz o upload do TXT final de volta pro S3, e marca o job como `completed` no banco.
- **Prós**: Resiliência extrema e escala assimétrica. Você pode subir 10 Pods baratos e velozes do FastAPI para receber tráfego, enquanto mantém apenas 2 Pods pesados (com acesso à GPU NVIDIA) rodando a inferência no seu próprio ritmo sem risco de derrubar o site web. Falhas na inferência fazem a mensagem voltar pra fila e tentar de novo.
- **Contras**: Esforço de reestruturação de código (implementação de padrão Pub/Sub e clients S3) e custo operacional de manter as infraestruturas de fila, banco e storage ativas.
