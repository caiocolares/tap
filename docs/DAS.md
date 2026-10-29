# Documento de Arquitetura de Software — T.A.P.

## Produto e escopo

T.A.P. transcreve áudio em TXT/JSON e identifica mudanças de falante com rótulos genéricos. É consumido por CLI e HTTP; não reconhece a identidade real dos falantes nem traduz conteúdo. Escopo e exemplos estão no [README](../README.md).

## Requisitos e atributos de qualidade

O processamento assíncrono deve sobreviver à troca de processos da API e à queda de um worker, enquanto PostgreSQL e MinIO preservarem seus dados. A recuperação repete a inferência inteira e respeita o limite de tentativas. SLA, RTO/RPO, p95/p99 e volumetria de referência: **A definir com stakeholders**.

Python 3.13, FastAPI, psycopg, faster-whisper e Pyannote são declarados em `pyproject.toml`; `uv.lock` registra a resolução. Ruff e pytest são executados na CI. A inferência usa CPU, CUDA ou MPS conforme o componente e a configuração.

A API usa JWT HS256 com expiração obrigatória, segredo configurado e envio do token somente por SMTP. Cada job tem um proprietário e consultas de outros usuários retornam 404. Pedidos de acesso são limitados por e-mail/IP, com contadores compartilhados no PostgreSQL quando disponível. O transporte TLS de PostgreSQL é configurável na URL de conexão, e o de MinIO por `MINIO_SECURE`. Credenciais e HF_TOKEN são injetados por ambiente/Secret; não entram nos jobs.

## Visão arquitetural

Os diagramas editáveis seguem C4: [contexto](c4/contexto.drawio) e [contêineres](c4/containers.drawio). A decisão de fila e recuperação está na [ADR-0001](adr/0001-fila-duravel-de-transcricao-no-postgresql.md).

- `server.py`: streaming de upload, admissão e consulta de jobs; a rota síncrona pode usar inferência local em imagens completas.
- `jobs.py` e `migrations/`: fila transacional, metadados, reservas, retomadas, tentativas e expiração.
- `worker.py`: consumo, heartbeat, download, inferência e publicação condicionada à reserva.
- `auth.py` e `mail.py`: autenticação, limitação de pedidos e transporte SMTP.
- `notifications.py`: entrega de resultados por e-mail, com reserva e tentativas independentes da inferência.
- `processing.py` e `transcribe.py`: cache por modelo, conversão, transcrição, diarização e escrita de resultados.
- `storage.py`: acesso compartilhado ao object storage. `settings.py`: configuração validada.

## Persistência e ciclo de vida

`tap_jobs` contém proprietário, estado da notificação, parâmetros, estado, contagem de tentativas, token/validade da reserva e referências aos objetos. A fila é a própria tabela, com seleção concorrente por `SKIP LOCKED`. O PostgreSQL confirma estado e enfileiramento na mesma transação; publicação de arquivos e metadados é coordenada por token e usa chaves por tentativa.

Metadados terminais expiram por `JOB_TTL_SECONDS`. A API faz a limpeza periódica. Objetos permanecem sujeitos ao lifecycle do bucket; arquivos temporários de cada execução são removidos ao encerrar normalmente. Quedas abruptas podem deixar temporários locais; a duração do volume efêmero do pod e sua limpeza operacional precisam ser consideradas.

O Compose usa volumes `postgres_data` e `minio_data`. Backup, restauração, retenção de objetos e alta disponibilidade da infraestrutura: **A definir com stakeholders/DBA**. Remover volumes pode perder jobs e arquivos.

## Infraestrutura, implantação e operação

O Compose executa API leve, worker CPU, notificador, PostgreSQL e MinIO compilado de uma release fixa do código oficial. `Dockerfile.api` não instala ML e define `API_ASYNC_ONLY=true`. As imagens CPU/GPU completas executam workers com `python -m worker` e preservam a opção de API síncrona.

No OpenShift, `knative-service.yaml` permite múltiplas réplicas e scale-to-zero da API. Os manifests em `deploy/` executam workers em Deployments independentes. O Secret `tap-runtime` fornece JWT_SECRET, SMTP, banco e object storage compartilhados. O notificador usa a imagem leve e um Deployment próprio. As migrações são aplicadas sob trava na inicialização da API e dos workers.

`/health` verifica o processo. `/ready` consulta banco e storage quando a fila está configurada. Logs incluem job e tentativa; não há instrumentação OpenTelemetry nesta entrega. A CI executa lint, testes e integrações com PostgreSQL/MinIO; as verificações de segurança estão em `.github/workflows/seguranca.yml`.

Notificações são selecionadas somente após a conclusão da transcrição, com reserva, heartbeat e tentativas próprias. Falhas SMTP preservam o resultado concluído. O envio é pelo menos uma vez: uma confirmação ambígua após aceitação pelo SMTP pode gerar duplicata. Jobs anteriores à migração de propriedade mantêm owner_email nulo e não são expostos pela API. `tap_auth_limits` armazena apenas chaves derivadas por hash e contadores temporários.

## Governança e histórico

- [ADR-0001 — fila PostgreSQL](adr/0001-fila-duravel-de-transcricao-no-postgresql.md): metadados e fila transacionais, reservas com recuperação e publicação protegida por token.
- **29/10/2026:** documento criado após inspeção do código, Compose, manifests e testes. O detector da skill não reconhece a stack Python; a descrição acima se baseia nos arquivos reais.

- [ADR-0002 — autenticação e notificações](adr/0002-integrar-autenticacao-e-notificacoes-a-fila-postgresql.md): integração dos recursos remotos à fila vigente e isolamento por proprietário.
