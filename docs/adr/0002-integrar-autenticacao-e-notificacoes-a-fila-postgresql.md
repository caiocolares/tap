# ADR-0002: Integrar autenticação e notificações à fila PostgreSQL

## Status

- **Status:** Aceito para esta implementação, sujeito à revisão do projeto.
- **Data:** 29/10/2026.
- **Autoria:** implementação assistida por Codex, conforme solicitação do responsável pelo repositório.

## Contexto

A integração com develop reuniu duas implementações incompatíveis de processamento assíncrono, rotas duplicadas e marcadores de merge em código e manifests. A evolução remota também trouxe autenticação por e-mail, entrega de transcrições por SMTP e o modelo padrão small. Era necessário preservar esses comportamentos junto da recuperação durável já documentada na ADR-0001.

## Decisão

Mantemos PostgreSQL como fila e repositório de jobs, conforme a ADR-0001. Removemos o consumidor RabbitMQ que redirecionava a inferência para uma rota HTTP interna. Workers continuam executando inferência diretamente, com reserva e heartbeat.

A API usa JWT HS256 com assinatura verificada, sub contendo e-mail válido e exp obrigatório. JWT_SECRET não tem valor padrão e precisa ter pelo menos 32 bytes. Tokens são enviados por SMTP, sem retorno no JSON ou registro em logs. Pedidos de acesso possuem limites por e-mail e IP, transacionais e compartilhados no PostgreSQL; o modo síncrono sem banco utiliza limite local e limitado em memória.

Persistimos owner_email em cada nova submissão. Consulta e download exigem o mesmo proprietário; jobs desconhecidos, de outro usuário ou antigos sem dono retornam 404. A migração preserva os dados antigos sem atribuir propriedade por suposição.

Notificações de transcrições são registradas no mesmo job e só se tornam elegíveis para envio após a conclusão. O processo separado python -m notifications usa reservas e tentativas próprias; uma falha SMTP não modifica o resultado nem reexecuta a inferência. A configuração de e-mail e JWT não é persistida nos registros de jobs.

## Consequências

- A API requer JWT_SECRET configurado. SMTP é necessário para emitir códigos de acesso; indisponibilidade retorna 503 em vez de simular sucesso.
- O Compose passa a executar um notificador leve além da API e do worker. OpenShift possui Deployment próprio para notificações.
- O transporte SMTP possui timeout e modo TLS explícitos. O padrão é STARTTLS; TLS implícito e modo local sem TLS são configurações distintas.
- A entrega por SMTP é pelo menos uma vez. Uma queda depois da aceitação da mensagem, antes da confirmação no banco, pode causar reenvio. Message-ID estável não é garantia de deduplicação pelo provedor.
- A retenção do job limita a janela de entrega. Notificações vencidas ou com tentativas esgotadas não reabrem a transcrição.
- O modelo padrão small é mantido na configuração compartilhada e na CLI.
- Testes cobrem JWT, isolamento por proprietário, limitação concorrente de pedidos, migração de dados antigos, recuperação de jobs/notificações e integridade dos manifests. Os testes SMTP usam transporte simulado; não enviam mensagens a pessoas.

## Histórico e Revisões

- **29/10/2026:** integração registrada após a resolução dos conflitos e definição de testes de regressão.
