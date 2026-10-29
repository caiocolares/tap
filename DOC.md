# Arquitetura do T.A.P.

O documento de arquitetura vigente está em [docs/DAS.md](docs/DAS.md).

- [ADR-0001](docs/adr/0001-fila-duravel-de-transcricao-no-postgresql.md): escolha da fila PostgreSQL e garantias de recuperação.
- [C4 — contexto](docs/c4/contexto.drawio) e [C4 — contêineres](docs/c4/containers.drawio): topologia editável.
- [README](README.md): configuração, execução da API e dos workers, testes e exemplos HTTP.

Jobs assíncronos usam PostgreSQL e MinIO compartilhados. A inferência é executada por workers separados, com reservas temporárias renovadas por heartbeat. Quedas permitem nova tentativa; um token impede que workers antigos publiquem sobre o resultado vigente. Consulte a ADR para limites, retenção e semântica de processamento pelo menos uma vez.
