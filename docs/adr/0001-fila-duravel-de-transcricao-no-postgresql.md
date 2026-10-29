# ADR-0001: Fila durável de transcrição no PostgreSQL

## Status

- **Status:** Aceito para esta implementação, sujeito à revisão do projeto.
- **Data:** 29/10/2026.
- **Autoria:** implementação assistida por Codex, conforme solicitação do responsável pelo repositório.

## Contexto

A API mantinha jobs em memória e executava inferência em BackgroundTasks. Reinícios perdiam o estado e o processamento; réplicas diferentes não conseguiam atender o polling, mesmo com arquivos no MinIO. Uma configuração de réplica única reduzia inconsistências, mas não recuperava trabalhos interrompidos.

## Decisão

Usamos PostgreSQL para metadados e fila, com uma linha por job. Enfileirar e registrar o estado é uma única transação, evitando o intervalo entre commit no banco e publicação em um broker separado. Usamos MinIO/S3 para entrada e resultados e processos `python -m worker` para executar inferência.

Workers reservam jobs com `FOR UPDATE SKIP LOCKED`, validade temporal e token por tentativa. Heartbeats renovam a reserva. Uma reserva vencida permite nova tentativa; conclusão, falha e renovação exigem token vigente e reserva ainda válida. O tempo usado para reservas e expiração é o do PostgreSQL.

Resultados são gravados em chaves distintas por tentativa. Somente a tentativa com reserva vigente pode registrar o resultado no job. O processamento é pelo menos uma vez: uma inferência pode se repetir após falha, mas um worker antigo não substitui o resultado de outro.

As opções modelo, idioma e diarização são persistidas na submissão. Tokens e credenciais permanecem no ambiente. Mantemos as rotas e o contrato HTTP assíncrono existentes; fila e processamento são apresentados como `processing`.

## Consequências

- **Benefícios:** recuperação após quedas, polling entre réplicas, limite global de admissão e escala independente dos workers. Nenhum broker adicional é necessário nesta etapa.
- **Custos:** PostgreSQL e object storage passam a ser obrigatórios para a API assíncrona. Há polling e conexões curtas ao banco; alta volumetria pode justificar pool de conexões e outra estratégia de distribuição.
- **Limites:** MinIO e PostgreSQL não compartilham transação. Uploads sem job confirmado e resultados de tentativas abandonadas podem ficar órfãos. Lifecycle do bucket deve removê-los sem antecipar a retenção dos jobs. Respostas ambíguas de commit preservam o objeto para não invalidar um job confirmado.
- **Recuperação:** tentativas e retomadas são limitadas por `max_attempts`; falhas definitivas também expiram. Não há checkpoint interno da inferência nem deduplicação entre POSTs distintos.
- **Operação:** volumes e backups devem preservar PostgreSQL e MinIO. O deployment da API pode escalar a zero; workers devem permanecer ativos para consumir a fila. Migrações são versionadas e serializadas na inicialização.
- **Validação:** testes PostgreSQL cobrem concorrência, fencing, backoff e expiração; um teste API/PostgreSQL/MinIO encerra um worker durante inferência simulada e verifica retomada e download após nova sessão da API.

## Histórico e Revisões

- **29/10/2026:** decisão registrada junto da implementação e dos testes de recuperação.
