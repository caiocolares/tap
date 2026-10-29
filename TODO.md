# Evolução do T.A.P.

A fila durável e a recuperação de trabalhos estão implementadas em `jobs.py` e `worker.py`. A API pode atender polling em várias réplicas com PostgreSQL e MinIO compartilhados. Detalhes na [ADR-0001](docs/adr/0001-fila-duravel-de-transcricao-no-postgresql.md) e no [DAS](docs/DAS.md).

## Próximas melhorias

- Estabelecer e testar políticas de backup/restauração e lifecycle de objetos; sua retenção deve cobrir fila, tentativas e disponibilidade dos resultados.
- Medir latência, espera e utilização dos workers antes de definir autoscaling e metas operacionais.
- Adicionar integração periódica com modelos reais e áudios de referência para medir transcrição e diarização.
- Fixar a resolução das variantes CPU de Torch/Torchaudio/TorchCodec e validar imagens completas com inferência real.
- Considerar pool de conexões, notificações e outras formas de distribuição quando o polling PostgreSQL se tornar um gargalo medido.
- Evoluir o contrato HTTP com status/download separados e idempotência de submissão. Reenviar o POST atualmente cria outro job.
- Definir cancelamento e timeout da inferência completa; a recuperação atual reexecuta o trabalho inteiro, sem checkpoint.

A integração de JWT e e-mail está documentada na [ADR-0002](docs/adr/0002-integrar-autenticacao-e-notificacoes-a-fila-postgresql.md). Cada job tem proprietário e a fila de notificações usa tentativas independentes da inferência.
